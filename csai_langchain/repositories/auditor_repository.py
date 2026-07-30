import re
import sqlite3
from collections import Counter

import pandas as pd

from csai_langchain.config.settings import (
    AUDITORS_DB,
)


class AuditorRepository:

    TABLE_NAME = "Sheet1"

    RESULT_COLUMNS = [
        "Company Name",
        "Reg No",
        "Financial Year End",
        "Auditor Firm No",
        "Auditor Name",
        "Auditor Address",
    ]

    def __init__(self):

        self.db = AUDITORS_DB

    ####################################################
    # Normalize
    ####################################################

    @staticmethod
    def _clean_value(value):

        if (
            value is None
            or pd.isna(value)
        ):
            return None

        return value

    @staticmethod
    def normalize_company(value):

        if (
            value is None
            or pd.isna(value)
        ):
            return ""

        value = str(
            value
        ).upper()

        value = value.replace(
            "&",
            " AND "
        )

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

    @staticmethod
    def _collapse_initials(tokens):

        collapsed = []
        index = 0

        while index < len(tokens):

            if (
                len(tokens[index]) == 1
                and index + 1 < len(tokens)
                and len(tokens[index + 1]) == 1
            ):

                initials = []

                while (
                    index < len(tokens)
                    and len(tokens[index]) == 1
                ):

                    initials.append(
                        tokens[index]
                    )

                    index += 1

                collapsed.append(
                    "".join(initials)
                )

                continue

            collapsed.append(
                tokens[index]
            )

            index += 1

        return collapsed

    @classmethod
    def normalize_auditor(
        cls,
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

        value = value.replace(
            "&",
            " AND "
        )

        value = re.sub(
            r"[^A-Z0-9\s]",
            " ",
            value
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        ).strip()

        tokens = cls._collapse_initials(
            value.split()
        )

        return " ".join(
            tokens
        )

    ####################################################
    # Read and validate database
    ####################################################

    def _read_all(self):

        if not self.db.is_file():

            raise FileNotFoundError(
                "Auditor database was not found: "
                f"{self.db}"
            )

        database_uri = (
            self.db.resolve().as_uri()
            + "?mode=ro"
        )

        connection = sqlite3.connect(
            database_uri,
            uri=True
        )

        try:
            table = connection.execute(
                (
                    "SELECT name "
                    "FROM sqlite_master "
                    "WHERE type = 'table' "
                    "AND name = ?"
                ),
                (
                    self.TABLE_NAME,
                )
            ).fetchone()

            if not table:

                raise ValueError(
                    "Auditor database table was not found: "
                    f"{self.TABLE_NAME}"
                )

            columns = [
                row[1]

                for row in connection.execute(
                    (
                        "PRAGMA table_info("
                        f'"{self.TABLE_NAME}"'
                        ")"
                    )
                )
            ]

            missing = [
                column

                for column in self.RESULT_COLUMNS

                if column not in columns
            ]

            if missing:

                raise ValueError(
                    "Auditor database is missing required "
                    f"column(s): {missing}"
                )

            selected_columns = ", ".join(
                f'"{column}"'
                for column in self.RESULT_COLUMNS
            )

            return pd.read_sql_query(
                (
                    f"SELECT {selected_columns} "
                    f'FROM "{self.TABLE_NAME}"'
                ),
                connection
            )

        finally:

            connection.close()

    ####################################################
    # Auditor grouping
    ####################################################

    def _with_auditor_groups(
        self,
        frame
    ):

        frame = frame.copy()

        frame["_row_order"] = range(
            len(frame)
        )

        frame["_raw_auditor"] = (
            frame["Auditor Name"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        frame["_auditor_base"] = (
            frame["_raw_auditor"]
            .apply(
                self.normalize_auditor
            )
        )

        base_names = {
            value

            for value in frame["_auditor_base"]

            if value
        }

        def group_key(value):

            tokens = value.split()

            if (
                len(tokens) > 1
                and len(tokens[-1]) == 1
            ):

                clean_base = " ".join(
                    tokens[:-1]
                )

                if clean_base in base_names:
                    return clean_base

            return value

        frame["_auditor_key"] = (
            frame["_auditor_base"]
            .apply(
                group_key
            )
        )

        canonical_names = {}

        for key, group in frame[
            frame["_auditor_key"] != ""
        ].groupby(
            "_auditor_key",
            sort=False
        ):

            counts = Counter(
                group["_raw_auditor"]
            )

            first_positions = (
                group.groupby(
                    "_raw_auditor",
                    sort=False
                )["_row_order"]
                .min()
                .to_dict()
            )

            canonical_names[key] = min(
                counts,
                key=lambda name: (
                    -counts[name],
                    first_positions[name],
                )
            )

        frame["_canonical_auditor"] = (
            frame["_auditor_key"]
            .map(
                canonical_names
            )
            .fillna("")
        )

        registration_numbers = (
            frame["Reg No"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        company_names = (
            frame["Company Name"]
            .apply(
                self.normalize_company
            )
        )

        frame["_company_identity"] = (
            registration_numbers.where(
                registration_numbers != "",
                company_names
            )
        )

        return frame

    def _resolve_auditor_key(
        self,
        frame,
        auditor_name
    ):

        target = self.normalize_auditor(
            auditor_name
        )

        if not target:
            return ""

        available = {
            value

            for value in frame["_auditor_key"]

            if value
        }

        tokens = target.split()

        if (
            len(tokens) > 1
            and len(tokens[-1]) == 1
        ):

            clean_base = " ".join(
                tokens[:-1]
            )

            if clean_base in available:
                target = clean_base

        if target in available:
            return target

        partial = {
            value

            for value in available

            if (
                target in value
                or value in target
            )
        }

        if len(partial) != 1:
            return ""

        return next(
            iter(
                partial
            )
        )

    ####################################################
    # Records
    ####################################################

    def _records(
        self,
        frame
    ):

        records = []

        for _, row in frame.iterrows():

            record = {}

            for column in self.RESULT_COLUMNS:

                value = row.get(
                    column
                )

                if column == "Auditor Name":

                    canonical = row.get(
                        "_canonical_auditor",
                        ""
                    )

                    if canonical:
                        value = canonical

                record[column] = self._clean_value(
                    value
                )

            records.append(
                record
            )

        return records

    def get_all_records(self):

        frame = self._read_all()

        if frame.empty:
            return []

        return self._records(
            self._with_auditor_groups(
                frame
            )
        )

    ####################################################
    # Company to auditor
    ####################################################

    def get_auditor_for_company(
        self,
        company_name
    ):

        target = self.normalize_company(
            company_name
        )

        if not target:
            return []

        frame = self._with_auditor_groups(
            self._read_all()
        )

        frame["_company_key"] = (
            frame["Company Name"]
            .apply(
                self.normalize_company
            )
        )

        matches = frame[
            frame["_company_key"]
            == target
        ].copy()

        if matches.empty:

            partial = frame[
                frame["_company_key"].str.contains(
                    target,
                    case=False,
                    regex=False,
                    na=False
                )
            ].copy()

            matched_companies = (
                partial["_company_key"]
                .dropna()
                .unique()
            )

            if len(matched_companies) != 1:
                return []

            matches = partial

        matches = matches.drop_duplicates(
            subset=[
                "_company_identity"
            ],
            keep="first"
        )

        return self._records(
            matches
        )

    ####################################################
    # Auditor to companies
    ####################################################

    def resolve_auditor_name(
        self,
        auditor_name
    ):

        frame = self._with_auditor_groups(
            self._read_all()
        )

        key = self._resolve_auditor_key(
            frame,
            auditor_name
        )

        if not key:
            return ""

        rows = frame[
            frame["_auditor_key"]
            == key
        ]

        if rows.empty:
            return ""

        return str(
            rows["_canonical_auditor"].iloc[0]
        )

    def get_companies_by_auditor(
        self,
        auditor_name
    ):

        frame = self._with_auditor_groups(
            self._read_all()
        )

        key = self._resolve_auditor_key(
            frame,
            auditor_name
        )

        if not key:
            return []

        matches = frame[
            frame["_auditor_key"]
            == key
        ].copy()

        matches = matches.drop_duplicates(
            subset=[
                "_company_identity"
            ],
            keep="first"
        )

        matches = matches.sort_values(
            "Company Name",
            na_position="last"
        )

        return self._records(
            matches
        )

    ####################################################
    # Distinct auditors
    ####################################################

    def get_distinct_auditors(self):

        frame = self._with_auditor_groups(
            self._read_all()
        )

        frame = frame[
            frame["_auditor_key"] != ""
        ].copy()

        results = []

        for _, group in frame.groupby(
            "_auditor_key",
            sort=False
        ):

            companies = group.drop_duplicates(
                subset=[
                    "_company_identity"
                ],
                keep="first"
            )

            results.append({
                "Auditor Name": str(
                    group[
                        "_canonical_auditor"
                    ].iloc[0]
                ),
                "Company Count": len(
                    companies
                ),
            })

        results.sort(
            key=lambda row: row[
                "Auditor Name"
            ]
        )

        return results
