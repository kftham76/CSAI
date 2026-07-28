import re
import sqlite3

import pandas as pd

from csai_langchain.config.settings import (
    EBOS_DB,
)


class EBOSRepository:

    DATE_PRIORITY = (
        "Date Received",
        "PDF Date",
        "Date of Application",
        "Date of Data Recorded",
        "UpdatedAt",
    )

    OWNERSHIP_COLUMNS = (
        "Direct Ownership %",
        "Indirect Ownership %",
        "Voting Shares %",
    )

    def __init__(self):

        self.db = EBOS_DB

    ####################################################
    # Normalize text
    ####################################################

    @staticmethod
    def normalize(
        value
    ):

        if (
            value is None
            or pd.isna(value)
        ):
            return ""

        value = str(
            value
        ).upper()

        value = re.sub(
            r"[^A-Z0-9\s]",
            " ",
            value
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        )

        return value.strip()

    ####################################################
    # Parse date column
    ####################################################

    @staticmethod
    def parse_date_column(
        df,
        column
    ):

        if column not in df.columns:

            return pd.Series(
                pd.NaT,
                index=df.index,
                dtype="datetime64[ns]"
            )

        values = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace(
                {
                    "": pd.NA,
                    "NAN": pd.NA,
                    "NONE": pd.NA,
                    "-": pd.NA,
                }
            )
        )

        if column == "UpdatedAt":

            return pd.to_datetime(
                values,
                errors="coerce",
                dayfirst=False
            )

        return pd.to_datetime(
            values,
            errors="coerce",
            dayfirst=True
        )

    ####################################################
    # Convert percentage
    ####################################################

    @staticmethod
    def percentage_column(
        df,
        column
    ):

        if column not in df.columns:

            return pd.Series(
                0.0,
                index=df.index
            )

        values = (
            df[column]
            .fillna("")
            .astype(str)
            .str.replace(
                "%",
                "",
                regex=False
            )
            .str.replace(
                ",",
                "",
                regex=False
            )
            .str.strip()
        )

        return pd.to_numeric(
            values,
            errors="coerce"
        ).fillna(
            0.0
        )

    ####################################################
    # Read EBOS
    ####################################################

    def read_all(self):

        with sqlite3.connect(
            str(self.db)
        ) as conn:

            return pd.read_sql_query(
                "SELECT * FROM EBOS_Master",
                conn
            )

    ####################################################
    # Match company
    ####################################################

    def match_company_rows(
        self,
        df,
        company_name
    ):

        target = self.normalize(
            company_name
        )

        if not target:
            return df.iloc[
                0:0
            ].copy()

        df = df.copy()

        df["_company_std"] = (
            df["Company Name"]
            .apply(
                self.normalize
            )
        )

        ################################################
        # Exact normalized match
        ################################################

        exact = df[
            df["_company_std"]
            == target
        ].copy()

        if not exact.empty:
            return exact

        ################################################
        # Partial match only when unambiguous
        ################################################

        partial = df[
            df["_company_std"].str.contains(
                target,
                case=False,
                regex=False,
                na=False
            )
        ].copy()

        if partial.empty:
            return partial

        matched_companies = (
            partial["_company_std"]
            .dropna()
            .unique()
        )

        if len(
            matched_companies
        ) != 1:

            return df.iloc[
                0:0
            ].copy()

        return partial

    ####################################################
    # Current beneficial owners
    ####################################################

    def get_current_beneficial_owners(
        self,
        company_name
    ):

        df = self.read_all()

        if df.empty:
            return []

        if "Company Name" not in df.columns:
            return []

        df = self.match_company_rows(
            df,
            company_name
        )

        if df.empty:
            return []

        df = df.copy()

        ################################################
        # Remove completely duplicated EBOS rows
        ################################################

        duplicate_columns = [

            column

            for column in (
                "Company Name",
                "Submission No",
                "BO Status",
                "Name",
                "IC",
                "Direct Ownership %",
                "Voting Shares %",
                "Date Received",
                "PDF Date",
                "Date of Cessation",
            )

            if column in df.columns
        ]

        if duplicate_columns:

            df = df.drop_duplicates(
                subset=duplicate_columns,
                keep="last"
            )

        ################################################
        # Filing date
        ################################################

        filing_date = pd.Series(
            pd.NaT,
            index=df.index,
            dtype="datetime64[ns]"
        )

        for column in self.DATE_PRIORITY:

            parsed = self.parse_date_column(
                df,
                column
            )

            filing_date = (
                filing_date.fillna(
                    parsed
                )
            )

        df["_filing_date"] = (
            filing_date
        )

        # Missing dates are treated as the oldest records.
        df["_filing_sort"] = (
            df["_filing_date"]
            .fillna(
                pd.Timestamp(
                    "1900-01-01"
                )
            )
        )

        ################################################
        # Submission number
        ################################################

        if "Submission No" in df.columns:

            df["_submission_sort"] = (
                df["Submission No"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

        else:

            df["_submission_sort"] = ""

        ################################################
        # Person identity
        ################################################

        if "IC" in df.columns:

            ic_values = (
                df["IC"]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        else:

            ic_values = pd.Series(
                "",
                index=df.index
            )

        if "Name" in df.columns:

            name_values = (
                df["Name"]
                .apply(
                    self.normalize
                )
            )

        else:

            name_values = pd.Series(
                "",
                index=df.index
            )

        df["_identity"] = (
            ic_values.where(
                ic_values != "",
                name_values
            )
        )

        df = df[
            df["_identity"] != ""
        ].copy()

        if df.empty:
            return []

        ################################################
        # BO status
        ################################################

        if "BO Status" in df.columns:

            df["_status"] = (
                df["BO Status"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

        else:

            df["_status"] = ""

        cessation_date = (
            self.parse_date_column(
                df,
                "Date of Cessation"
            )
        )

        df["_is_cessation"] = (
            df["_status"].eq(
                "CESSATION"
            )
            |
            (
                df["_status"].eq("")
                &
                cessation_date.notna()
            )
        )

        ################################################
        # Status priority
        ################################################

        # When NEW and CESSATION occur in the same filing
        # for the same person, NEW represents the replacement
        # active ownership record.
        df["_status_priority"] = 2

        df.loc[
            df["_is_cessation"],
            "_status_priority"
        ] = 1

        df.loc[
            df["_status"].eq("NEW"),
            "_status_priority"
        ] = 3

        ################################################
        # Ownership score
        ################################################

        ownership_values = []

        for column in self.OWNERSHIP_COLUMNS:

            ownership_values.append(
                self.percentage_column(
                    df,
                    column
                )
            )

        if ownership_values:

            ownership_frame = pd.concat(
                ownership_values,
                axis=1
            )

            df["_ownership_score"] = (
                ownership_frame.max(
                    axis=1
                )
            )

        else:

            df["_ownership_score"] = 0.0

        ################################################
        # Stable original row order
        ################################################

        df["_row_order"] = range(
            len(df)
        )

        ################################################
        # Select latest event for each person
        ################################################

        df = df.sort_values(
            by=[
                "_filing_sort",
                "_submission_sort",
                "_status_priority",
                "_ownership_score",
                "_row_order",
            ],
            ascending=[
                True,
                True,
                True,
                True,
                True,
            ]
        )

        latest = (
            df.groupby(
                "_identity",
                sort=False,
                dropna=False
            )
            .tail(1)
            .copy()
        )

        ################################################
        # Exclude persons whose latest event is cessation
        ################################################

        latest = latest[
            ~latest["_is_cessation"]
        ].copy()

        if latest.empty:
            return []

        ################################################
        # Remove helper columns
        ################################################

        helper_columns = [
            column

            for column in latest.columns

            if column.startswith("_")
        ]

        latest = latest.drop(
            columns=helper_columns,
            errors="ignore"
        )

        ################################################
        # Stable output ordering
        ################################################

        if "Name" in latest.columns:

            latest = latest.sort_values(
                "Name",
                na_position="last"
            )

        return latest.to_dict(
            orient="records"
        )