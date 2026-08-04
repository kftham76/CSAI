import re
import sqlite3

import pandas as pd

from csai_langchain.config.settings import (
    CONSTITUTIONS_DB,
)
from csai_langchain.routing.capabilities import (
    DWR_FIELD,
    MWR_FIELD,
)


class ConstitutionRepository:

    TABLE_NAME = "Sheet1"

    REQUIRED_COLUMNS = [
        "Company Name",
        "Reg No",
        DWR_FIELD,
        MWR_FIELD,
    ]

    def __init__(self):

        self.db = CONSTITUTIONS_DB

    @staticmethod
    def normalize_company(value):

        if value is None or pd.isna(value):
            return ""

        value = str(value).upper().replace("&", " AND ")
        value = re.sub(r"[^A-Z0-9\s]", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _clean_value(value):

        if value is None or pd.isna(value):
            return None

        return value

    def _read_all(self):

        if not self.db.is_file():
            raise FileNotFoundError(
                "Constitution database was not found: "
                f"{self.db}"
            )

        database_uri = self.db.resolve().as_uri() + "?mode=ro"

        with sqlite3.connect(
            database_uri,
            uri=True,
        ) as connection:
            table = connection.execute(
                (
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name = ?"
                ),
                (self.TABLE_NAME,),
            ).fetchone()

            if not table:
                raise ValueError(
                    "Constitution database table was not "
                    f"found: {self.TABLE_NAME}"
                )

            columns = [
                row[1]
                for row in connection.execute(
                    f'PRAGMA table_info("{self.TABLE_NAME}")'
                )
            ]
            missing = [
                column
                for column in self.REQUIRED_COLUMNS
                if column not in columns
            ]

            if missing:
                raise ValueError(
                    "Constitution database is missing "
                    f"required column(s): {missing}"
                )

            return pd.read_sql_query(
                f'SELECT * FROM "{self.TABLE_NAME}"',
                connection,
            )

    @classmethod
    def _records(cls, frame, fields):

        columns = ["Company Name"]

        for field in fields:
            if field != "Company Name" and field not in columns:
                columns.append(field)

        available = [
            column for column in columns if column in frame.columns
        ]

        return [
            {
                column: cls._clean_value(row.get(column))
                for column in available
            }
            for row in frame.to_dict(orient="records")
        ]

    def get_all_company_names(self):

        frame = self._read_all()

        if frame.empty:
            return []

        return [
            {"Company Name": value}
            for value in frame["Company Name"].dropna().unique()
            if str(value).strip()
        ]

    def get_company_information(self, company_name, fields):

        target = self.normalize_company(company_name)

        if not target:
            return []

        frame = self._read_all()
        keys = frame["Company Name"].apply(
            self.normalize_company
        )
        matches = frame[keys == target].copy()

        if matches.empty:
            partial = frame[
                keys.str.contains(
                    target,
                    case=False,
                    regex=False,
                    na=False,
                )
            ].copy()

            if len(
                partial["Company Name"]
                .apply(self.normalize_company)
                .unique()
            ) != 1:
                return []

            matches = partial

        return self._records(matches, fields)

    def get_all_company_information(self, fields):

        frame = self._read_all()

        if frame.empty:
            return []

        frame = frame.sort_values(
            "Company Name",
            na_position="last",
        )

        return self._records(frame, fields)
