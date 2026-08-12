import re
import sqlite3

from csai_langchain.config.settings import NEW_INCORP_DB


class NewIncorpRepository:
    """Read the Excel-mirrored New_Incorp table without modifying it."""

    TABLE_NAME = "New_Incorp"

    def __init__(self):
        self.db = NEW_INCORP_DB

    @staticmethod
    def _normalize(value):
        text = str(value or "").upper()
        text = re.sub(r"[^A-Z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _connect(self):
        if not self.db.is_file():
            raise FileNotFoundError(
                "New incorporation database was not found: "
                f"{self.db}"
            )
        return sqlite3.connect(
            self.db.resolve().as_uri() + "?mode=ro",
            uri=True,
        )

    def _read_all(self):
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (self.TABLE_NAME,),
            ).fetchone()
            if table is None:
                raise ValueError(
                    "New incorporation database table was not found: "
                    f"{self.TABLE_NAME}"
                )
            rows = connection.execute(
                f'SELECT * FROM "{self.TABLE_NAME}" ORDER BY rowid'
            ).fetchall()
        return [dict(row) for row in rows]

    def get_company(self, company_name):
        requested = str(company_name or "").strip()
        target = self._normalize(requested)
        if not target:
            return []

        rows = self._read_all()
        exact = [
            row
            for row in rows
            if self._normalize(row.get("Company Name")) == target
        ]
        if exact:
            return exact

        partial = [
            row
            for row in rows
            if target in self._normalize(row.get("Company Name"))
        ]
        matched_names = {
            self._normalize(row.get("Company Name"))
            for row in partial
        }
        return partial if len(matched_names) == 1 else []
