import re
import sqlite3

import pandas as pd

from csai_langchain.config.settings import (
    CLIENT_DB,
)


class CompanyRepository:

    def __init__(self):

        self.db = CLIENT_DB

    ####################################################
    # Normalize
    ####################################################

    @staticmethod
    def _normalize(name):

        if (
            name is None
            or pd.isna(name)
        ):
            return ""

        name = str(
            name
        ).upper()

        name = re.sub(
            r"[^A-Z0-9\s]",
            " ",
            name
        )

        name = re.sub(
            r"\s+",
            " ",
            name
        )

        return name.strip()

    ####################################################
    # Read client master
    ####################################################

    def _read_all(self):

        with sqlite3.connect(
            str(self.db)
        ) as conn:

            return pd.read_sql_query(
                "SELECT * FROM Client_Master",
                conn
            )

    ####################################################
    # Get company
    ####################################################

    def get_company(
        self,
        company_name
    ):

        company_name = (
            company_name
            or ""
        ).strip()

        # Prevent an empty string from matching every row.
        if not company_name:
            return []

        target = self._normalize(
            company_name
        )

        if not target:
            return []

        df = self._read_all()

        if (
            df.empty
            or "Company Name" not in df.columns
        ):
            return []

        df = df.copy()

        df["search_name"] = (
            df["Company Name"]
            .fillna("")
            .apply(
                self._normalize
            )
        )

        ################################################
        # Exact normalized match
        ################################################

        exact_result = df[
            df["search_name"]
            == target
        ].copy()

        if not exact_result.empty:

            exact_result = exact_result.drop(
                columns=[
                    "search_name"
                ],
                errors="ignore"
            )

            return exact_result.to_dict(
                orient="records"
            )

        ################################################
        # Partial match only when unambiguous
        ################################################

        partial_result = df[
            df["search_name"].str.contains(
                target,
                case=False,
                regex=False,
                na=False
            )
        ].copy()

        if partial_result.empty:
            return []

        matched_companies = (
            partial_result[
                "search_name"
            ]
            .dropna()
            .unique()
        )

        # Never select an arbitrary company when several
        # companies match the partial name.
        if len(
            matched_companies
        ) != 1:
            return []

        partial_result = partial_result.drop(
            columns=[
                "search_name"
            ],
            errors="ignore"
        )

        return partial_result.to_dict(
            orient="records"
        )

    ####################################################
    # Get all companies
    ####################################################

    def get_all_companies(self):

        df = self._read_all()

        if df.empty:
            return []

        return df.to_dict(
            orient="records"
        )

    ####################################################
    # Get all company names
    ####################################################

    def get_all_company_names(self):

        df = self._read_all()

        if (
            df.empty
            or "Company Name" not in df.columns
        ):
            return []

        companies = {}

        for value in df["Company Name"]:

            if (
                value is None
                or pd.isna(value)
            ):
                continue

            company_name = str(
                value
            ).strip()

            normalized_name = self._normalize(
                company_name
            )

            if (
                not company_name
                or not normalized_name
                or normalized_name in companies
            ):
                continue

            # Preserve the spelling from the first
            # database row for each logical company.
            companies[
                normalized_name
            ] = company_name

        return [
            {
                "Company Name": company_name
            }
            for company_name in sorted(
                companies.values(),
                key=lambda name: (
                    self._normalize(name),
                    name
                )
            )
        ]

    ####################################################
    # Person directorship
    ####################################################

    def get_person_directorship(
        self,
        person_name
    ):

        person_name = (
            person_name
            or ""
        ).strip()

        # Prevent empty person names from matching records.
        if not person_name:
            return []

        person = self._normalize(
            person_name
        )

        if not person:
            return []

        companies = self.get_all_companies()

        results = []

        for row in companies:

            for index in range(
                1,
                50
            ):

                key = (
                    f"Director{index} Name"
                )

                if key not in row:
                    break

                name = row.get(
                    key
                )

                if (
                    name is None
                    or pd.isna(name)
                ):
                    continue

                normalized_name = (
                    self._normalize(
                        name
                    )
                )

                if normalized_name == person:

                    results.append({
                        "Company Name": row.get(
                            "Company Name"
                        ),
                        "Reg No": row.get(
                            "Reg No"
                        )
                    })

                    break

        return results
