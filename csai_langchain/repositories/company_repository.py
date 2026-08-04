import re
import sqlite3

import pandas as pd

from csai_langchain.config.settings import (
    CLIENT_DB,
)


class CompanyRepository:

    CLIENT_TABLE = "Client_Master"

    RAW_TABLES = {
        "Extraction_Issues",
        "Statutory_Documents",
        "Statutory_Events",
    }

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

    @staticmethod
    def _clean_value(value):

        if value is None or pd.isna(value):
            return None

        return value

    @classmethod
    def _records(cls, frame):

        if frame.empty:
            return []

        return [
            {
                column: cls._clean_value(value)
                for column, value in row.items()
            }
            for row in frame.to_dict(orient="records")
        ]

    def _connect(self):

        if not self.db.is_file():
            raise FileNotFoundError(
                "Client database was not found: "
                f"{self.db}"
            )

        database_uri = self.db.resolve().as_uri() + "?mode=ro"

        return sqlite3.connect(
            database_uri,
            uri=True
        )

    def _read_table(self, table_name, folder=None):

        allowed_tables = {
            self.CLIENT_TABLE,
            *self.RAW_TABLES,
        }

        if table_name not in allowed_tables:
            raise ValueError(
                "Unsupported client database table: "
                f"{table_name}"
            )

        with self._connect() as conn:

            table = conn.execute(
                (
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name = ?"
                ),
                (table_name,)
            ).fetchone()

            if not table:
                raise ValueError(
                    "Client database table was not found: "
                    f"{table_name}"
                )

            query = f'SELECT * FROM "{table_name}"'
            parameters = ()

            if folder is not None:
                query += ' WHERE "Folder" = ?'
                parameters = (folder,)

            if table_name in self.RAW_TABLES:
                query += ' ORDER BY "Folder", rowid'

            return pd.read_sql_query(
                query,
                conn,
                params=parameters
            )

    ####################################################
    # Read client master
    ####################################################

    def _read_all(self):

        return self._read_table(
            self.CLIENT_TABLE
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

            return self._records(
                exact_result
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

        return self._records(
            partial_result
        )

    ####################################################
    # Get all companies
    ####################################################

    def get_all_companies(self):

        df = self._read_all()

        if df.empty:
            return []

        df = df.sort_values(
            "Company Name",
            na_position="last"
        )

        return self._records(
            df
        )

    def get_all_annual_return_dates(self):

        df = self._read_all()

        required_columns = [
            "Company Name",
            "Annual Return Date",
        ]

        if (
            df.empty
            or any(
                column not in df.columns
                for column in required_columns
            )
        ):
            return []

        df = df[required_columns].sort_values(
            "Company Name",
            na_position="last"
        )

        return self._records(
            df
        )

    def get_annual_return_date(self, company_name):

        rows = self.get_company(
            company_name
        )

        return [
            {
                "Company Name": row.get(
                    "Company Name"
                ),
                "Annual Return Date": row.get(
                    "Annual Return Date"
                ),
            }
            for row in rows
        ]

    def _project_company_information(
        self,
        rows,
        fields
    ):

        requested_fields = []

        for field in fields:

            if (
                field == "Company Name"
                or field in requested_fields
            ):
                continue

            requested_fields.append(
                field
            )

        columns = [
            "Company Name",
            *requested_fields,
        ]

        return [
            {
                column: row.get(column)
                for column in columns
            }
            for row in rows
        ]

    def get_all_company_information(self, fields):

        rows = self.get_all_companies()

        if not rows:
            return []

        available_columns = set(
            rows[0]
        )

        valid_fields = [
            field
            for field in fields
            if field in available_columns
        ]

        if not valid_fields:
            return []

        return self._project_company_information(
            rows,
            valid_fields
        )

    def get_company_information(
        self,
        company_name,
        fields
    ):

        rows = self.get_company(
            company_name
        )

        if not rows:
            return []

        available_columns = set(
            rows[0]
        )

        valid_fields = [
            field
            for field in fields
            if field in available_columns
        ]

        if not valid_fields:
            return []

        return self._project_company_information(
            rows,
            valid_fields
        )

    def _resolve_company_folder(self, company_name):

        rows = self.get_company(
            company_name
        )

        if not rows:
            return ""

        folder = rows[0].get(
            "Folder"
        )

        if folder is None or pd.isna(folder):
            return ""

        return str(folder).strip()

    def _get_raw_records(
        self,
        table_name,
        company_name=None
    ):

        folder = None

        if company_name is not None:
            folder = self._resolve_company_folder(
                company_name
            )

            if not folder:
                return []

        frame = self._read_table(
            table_name,
            folder=folder
        )

        return self._records(
            frame
        )

    def get_all_extraction_issues(self):

        return self._get_raw_records(
            "Extraction_Issues"
        )

    def get_extraction_issues_for_company(
        self,
        company_name
    ):

        return self._get_raw_records(
            "Extraction_Issues",
            company_name
        )

    def get_all_statutory_documents(self):

        return self._get_raw_records(
            "Statutory_Documents"
        )

    def get_statutory_documents_for_company(
        self,
        company_name
    ):

        return self._get_raw_records(
            "Statutory_Documents",
            company_name
        )

    def get_all_statutory_events(self):

        return self._get_raw_records(
            "Statutory_Events"
        )

    def get_statutory_events_for_company(
        self,
        company_name
    ):

        return self._get_raw_records(
            "Statutory_Events",
            company_name
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
    # Complete director records
    ####################################################

    def _director_records(self, companies):

        results = []

        for row in companies:

            for index in range(1, 50):

                name_key = f"Director{index} Name"

                if name_key not in row:
                    break

                name = self._clean_value(
                    row.get(name_key)
                )

                if not str(name or "").strip():
                    continue

                results.append({
                    "Company Name": row.get(
                        "Company Name"
                    ),
                    "Reg No": row.get(
                        "Reg No"
                    ),
                    "Name": name,
                    "IC": self._clean_value(
                        row.get(f"Director{index} IC")
                    ),
                    "ID Type": self._clean_value(
                        row.get(f"Director{index} ID Type")
                    ),
                    "DOB": self._clean_value(
                        row.get(f"Director{index} DOB")
                    ),
                    "Passport Expiry": self._clean_value(
                        row.get(f"Director{index} Passport Expiry")
                    ),
                    "Nationality": self._clean_value(
                        row.get(
                            f"Director{index} Nationality"
                        )
                    ),
                    "Citizenship": self._clean_value(
                        row.get(f"Director{index} Citizenship")
                    ),
                    "Race": self._clean_value(
                        row.get(f"Director{index} Race")
                    ),
                    "Gender": self._clean_value(
                        row.get(f"Director{index} Gender")
                    ),
                    "Residential Address": self._clean_value(
                        row.get(
                            f"Director{index} Residential Address"
                        )
                    ),
                    "Service Address": self._clean_value(
                        row.get(
                            f"Director{index} Service Address"
                        )
                    ),
                    "Designation": self._clean_value(
                        row.get(f"Director{index} Designation")
                    ),
                    "Business Occupation": self._clean_value(
                        row.get(f"Director{index} Business Occupation")
                    ),
                    "Email": self._clean_value(
                        row.get(f"Director{index} Email")
                    ),
                    "Contact No": self._clean_value(
                        row.get(f"Director{index} Contact No")
                    ),
                    "Appointment Date": self._clean_value(
                        row.get(f"Director{index} Appointment Date")
                    ),
                })

        return sorted(
            results,
            key=lambda record: (
                self._normalize(
                    record.get("Company Name")
                ),
                self._normalize(
                    record.get("Name")
                ),
            )
        )

    def get_all_directors(self):

        return self._director_records(
            self.get_all_companies()
        )

    def get_directors_for_company(self, company_name):

        return self._director_records(
            self.get_company(company_name)
        )

    ####################################################
    # Complete shareholder records
    ####################################################

    def _shareholder_records(self, companies):

        results = []

        for row in companies:

            for index in range(1, 50):

                name_key = f"Member{index} Name"

                if name_key not in row:
                    break

                name = self._clean_value(
                    row.get(name_key)
                )

                if not str(name or "").strip():
                    continue

                results.append({
                    "Company Name": row.get(
                        "Company Name"
                    ),
                    "Reg No": row.get(
                        "Reg No"
                    ),
                    "Type": self._clean_value(
                        row.get(f"Member{index} Type")
                    ),
                    "Name": name,
                    "ID Type": self._clean_value(
                        row.get(f"Member{index} ID Type")
                    ),
                    "ID No": self._clean_value(
                        row.get(f"Member{index} ID No")
                    ),
                    "Nationality": self._clean_value(
                        row.get(
                            f"Member{index} Nationality"
                        )
                    ),
                    "Race": self._clean_value(
                        row.get(f"Member{index} Race")
                    ),
                    "Gender": self._clean_value(
                        row.get(f"Member{index} Gender")
                    ),
                    "DOB": self._clean_value(
                        row.get(f"Member{index} DOB")
                    ),
                    "Address": self._clean_value(
                        row.get(f"Member{index} Address")
                    ),
                    "Shares": self._clean_value(
                        row.get(f"Member{index} Shares")
                    ),
                    "Share Type": self._clean_value(
                        row.get(f"Member{index} Share Type")
                    ),
                    "Analysis": self._clean_value(
                        row.get(f"Member{index} Analysis")
                    ),
                })

        return sorted(
            results,
            key=lambda record: (
                self._normalize(
                    record.get("Company Name")
                ),
                self._normalize(
                    record.get("Name")
                ),
            )
        )

    def get_all_shareholders(self):

        return self._shareholder_records(
            self.get_all_companies()
        )

    def get_shareholders_for_company(self, company_name):

        return self._shareholder_records(
            self.get_company(company_name)
        )

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

        return [
            row
            for row in self.get_all_directors()
            if self._normalize(
                row.get("Name")
            ) == person
        ]

    ####################################################
    # Person shareholdings
    ####################################################

    def get_person_shareholdings(
        self,
        person_name
    ):

        person_name = (
            person_name
            or ""
        ).strip()

        if not person_name:
            return []

        person = self._normalize(
            person_name
        )

        if not person:
            return []

        results = []

        for row in self.get_all_shareholders():

            if self._normalize(
                row.get("Name")
            ) != person:
                continue

            results.append({
                "Status": "Current",
                **row,
            })

        return results

    ####################################################
    # Person company associations
    ####################################################

    def get_person_company_associations(
        self,
        person_name
    ):

        person_name = (
            person_name
            or ""
        ).strip()

        person = self._normalize(
            person_name
        )

        if not person:
            return []

        associations = {}

        def identity_for(row):

            registration = str(
                row.get(
                    "Reg No"
                )
                or ""
            ).strip()

            return (
                registration
                or self._normalize(
                    row.get(
                        "Company Name"
                    )
                )
            )

        def get_or_create(row):

            identity = identity_for(
                row
            )

            if not identity:
                return None

            if identity not in associations:

                associations[
                    identity
                ] = {
                    "Company Name": row.get(
                        "Company Name"
                    ),
                    "Reg No": row.get(
                        "Reg No"
                    ),
                    "Status": "Current",
                    "Name": person,
                    "Roles": [],
                }

            return associations[
                identity
            ]

        for row in self.get_person_directorship(
            person
        ):

            association = get_or_create(
                row
            )

            if (
                association is not None
                and "Director"
                not in association["Roles"]
            ):
                association[
                    "Roles"
                ].append(
                    "Director"
                )

        for row in self.get_person_shareholdings(
            person
        ):

            association = get_or_create(
                row
            )

            if association is None:
                continue

            if (
                "Shareholder"
                not in association["Roles"]
            ):
                association[
                    "Roles"
                ].append(
                    "Shareholder"
                )

            # Member details apply only to companies in
            # which the person appears in a MemberN group.
            association.update(
                row
            )
            association[
                "Roles"
            ] = [
                role
                for role in (
                    "Director",
                    "Shareholder",
                )
                if role in association[
                    "Roles"
                ]
            ]

        return sorted(
            associations.values(),
            key=lambda row: (
                self._normalize(
                    row.get(
                        "Company Name"
                    )
                ),
                str(
                    row.get(
                        "Reg No"
                    )
                    or ""
                ),
            )
        )
