"""Convert the auditors workbook into a standalone SQLite database."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


SOURCE_FILE = Path(r"D:\CSAI_DATA\Database\Auditors.xlsx")
SHEET_NAME = "Sheet1"
DATABASE_FILE = Path(r"C:\CSAI_OS\04 Python Tools\DB\auditors.db")

EXPECTED_COLUMNS = [
    "Company Name",
    "Reg No",
    "Financial Year End",
    "Auditor Firm No",
    "Auditor Name",
    "Auditor Address",
]


def load_workbook() -> pd.DataFrame:
    """Load and validate the configured Excel worksheet."""
    if not SOURCE_FILE.is_file():
        raise FileNotFoundError(f"Source workbook not found: {SOURCE_FILE}")

    with pd.ExcelFile(SOURCE_FILE, engine="openpyxl") as workbook:
        if SHEET_NAME not in workbook.sheet_names:
            available = ", ".join(workbook.sheet_names) or "(none)"
            raise ValueError(
                f"Worksheet {SHEET_NAME!r} was not found in {SOURCE_FILE}. "
                f"Available worksheets: {available}"
            )

        frame = pd.read_excel(
            workbook,
            sheet_name=SHEET_NAME,
            dtype=str,
            keep_default_na=False,
        )

    actual_columns = list(frame.columns)
    if actual_columns != EXPECTED_COLUMNS:
        missing = [column for column in EXPECTED_COLUMNS if column not in actual_columns]
        unexpected = [column for column in actual_columns if column not in EXPECTED_COLUMNS]
        raise ValueError(
            "Unexpected worksheet columns. "
            f"Expected, in order: {EXPECTED_COLUMNS}. "
            f"Found: {actual_columns}. "
            f"Missing: {missing or '(none)'}. "
            f"Unexpected: {unexpected or '(none)'}."
        )

    # dtype=str protects identifiers from numeric conversion. Convert only truly
    # empty Excel cells to None so SQLite stores them as SQL NULL.
    frame = frame[EXPECTED_COLUMNS].astype(object)
    frame = frame.where(frame.ne(""), None)
    frame["UpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return frame


def write_database(frame: pd.DataFrame) -> None:
    """Atomically replace the output database with the converted worksheet."""
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = DATABASE_FILE.with_name(f".{DATABASE_FILE.name}.tmp")

    if temp_file.exists():
        temp_file.unlink()

    try:
        connection = sqlite3.connect(temp_file)
        try:
            with connection:
                frame.to_sql(
                    SHEET_NAME,
                    connection,
                    if_exists="replace",
                    index=False,
                )
        finally:
            connection.close()

        os.replace(temp_file, DATABASE_FILE)
    except Exception:
        if temp_file.exists():
            temp_file.unlink()
        raise


def main() -> None:
    frame = load_workbook()
    write_database(frame)

    print(f"Source   : {SOURCE_FILE}")
    print(f"Database : {DATABASE_FILE}")
    print(f"Table    : {SHEET_NAME}")
    print(f"Rows     : {len(frame)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"ERROR: {error}") from error
