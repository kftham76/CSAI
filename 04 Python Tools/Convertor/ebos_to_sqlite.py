"""Convert the EBOS workbook into its runtime SQLite table."""

import os
from pathlib import Path
import shutil
import sqlite3

import pandas as pd


SOURCE_FILE = Path(r"D:\CSAI_DATA\Database\Ebos data.xlsx")
SHEET_NAME = "EBOS Data"
DATABASE_FILE = Path(r"C:\CSAI_OS\06 Data\databases\ebos_master.db")
TABLE_NAME = "EBOS_Master"

REQUIRED_COLUMNS = (
    "Company",
    "Company Name",
    "Company No",
    "Company Status",
    "BO1 Source PDF",
    "BO1 Name",
    "UpdatedAt",
)


def load_workbook() -> pd.DataFrame:
    """Read and validate the configured worksheet as text."""
    if not SOURCE_FILE.is_file():
        raise FileNotFoundError(f"Source workbook not found: {SOURCE_FILE}")

    with pd.ExcelFile(SOURCE_FILE, engine="openpyxl") as workbook:
        if SHEET_NAME not in workbook.sheet_names:
            available = ", ".join(workbook.sheet_names) or "(none)"
            raise ValueError(
                f"Worksheet {SHEET_NAME!r} was not found in {SOURCE_FILE}. "
                f"Available worksheets: {available}"
            )

        header = pd.read_excel(
            workbook,
            sheet_name=SHEET_NAME,
            header=None,
            nrows=1,
            dtype=object,
            keep_default_na=False,
        )
        if header.empty:
            raise ValueError(f"Worksheet {SHEET_NAME!r} is empty.")

        raw_columns = list(header.iloc[0])
        blank_columns = [
            position + 1
            for position, column in enumerate(raw_columns)
            if column is None or not str(column).strip()
        ]
        if blank_columns:
            raise ValueError(
                "The EBOS worksheet contains blank column headings at "
                f"positions: {blank_columns}"
            )

        normalized_columns = [str(column) for column in raw_columns]
        duplicate_columns = sorted(
            {
                column
                for column in normalized_columns
                if normalized_columns.count(column) > 1
            }
        )
        if duplicate_columns:
            raise ValueError(
                "The EBOS worksheet contains duplicate columns: "
                f"{', '.join(duplicate_columns)}"
            )

        frame = pd.read_excel(
            workbook,
            sheet_name=SHEET_NAME,
            dtype=str,
            keep_default_na=False,
        )

    actual_columns = list(frame.columns)
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in actual_columns
    ]
    if missing_columns:
        raise ValueError(
            "The EBOS worksheet is missing required columns: "
            f"{', '.join(missing_columns)}"
        )

    # Preserve nonblank source values exactly as text. Only empty or
    # whitespace-only Excel cells become SQL NULL.
    frame = frame.astype(object)
    for column in frame.columns:
        frame[column] = frame[column].map(
            lambda value: (
                None
                if value is None
                or pd.isna(value)
                or not str(value).strip()
                else str(value)
            )
        )

    return frame


def verify_table(
    connection: sqlite3.Connection,
    table_name: str,
    expected: pd.DataFrame,
) -> None:
    """Verify a converted table's schema, row count, values, and database."""
    quoted_table = f"[{table_name}]"
    table_info = list(
        connection.execute(f"PRAGMA table_info({quoted_table})")
    )
    imported_columns = [row[1] for row in table_info]
    imported_types = [row[2].upper() for row in table_info]
    imported_rows = connection.execute(
        f"SELECT COUNT(*) FROM {quoted_table}"
    ).fetchone()[0]

    if imported_columns != list(expected.columns):
        raise RuntimeError(f"Column validation failed for {table_name}.")
    if imported_rows != len(expected):
        raise RuntimeError(
            f"Row-count validation failed for {table_name}: "
            f"expected {len(expected)}, imported {imported_rows}."
        )
    if imported_types != ["TEXT"] * len(expected.columns):
        raise RuntimeError(
            f"Column-type validation failed for {table_name}; "
            "every column must use TEXT affinity."
        )

    imported = pd.read_sql_query(
        f"SELECT * FROM {quoted_table} ORDER BY rowid",
        connection,
    )
    if not expected.equals(imported):
        raise RuntimeError(f"Value validation failed for {table_name}.")

    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(
            f"SQLite integrity check failed for {table_name}: {integrity}"
        )


def replace_table_transactional(frame: pd.DataFrame) -> None:
    """Atomically swap the table when Windows locks the database file."""
    staging_table = f"__sync_{TABLE_NAME}"
    connection = sqlite3.connect(str(DATABASE_FILE), timeout=30)

    try:
        connection.execute(f"DROP TABLE IF EXISTS [{staging_table}]")
        connection.commit()

        frame.to_sql(
            staging_table,
            connection,
            if_exists="replace",
            index=False,
            dtype={column: "TEXT" for column in frame.columns},
        )
        verify_table(connection, staging_table, frame)

        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(f"DROP TABLE IF EXISTS [{TABLE_NAME}]")
            connection.execute(
                f"ALTER TABLE [{staging_table}] RENAME TO [{TABLE_NAME}]"
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        try:
            connection.execute(f"DROP TABLE IF EXISTS [{staging_table}]")
            connection.commit()
        finally:
            connection.close()


def write_database(frame: pd.DataFrame) -> None:
    """Replace the EBOS table atomically while preserving other tables."""
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = DATABASE_FILE.with_name(
        f".{DATABASE_FILE.stem}.sync.tmp.db"
    )

    if temp_file.exists():
        temp_file.unlink()

    if DATABASE_FILE.exists():
        shutil.copy2(DATABASE_FILE, temp_file)

    try:
        connection = sqlite3.connect(str(temp_file))
        try:
            with connection:
                frame.to_sql(
                    TABLE_NAME,
                    connection,
                    if_exists="replace",
                    index=False,
                    dtype={column: "TEXT" for column in frame.columns},
                )
            verify_table(connection, TABLE_NAME, frame)
        finally:
            connection.close()

        try:
            os.replace(temp_file, DATABASE_FILE)
        except PermissionError:
            replace_table_transactional(frame)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def main() -> None:
    frame = load_workbook()
    write_database(frame)

    print(f"Source    : {SOURCE_FILE}")
    print(f"Database  : {DATABASE_FILE}")
    print(f"Table     : {TABLE_NAME}")
    print(f"Rows      : {len(frame)}")
    print(f"Columns   : {len(frame.columns)}")
    print("Integrity : ok")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"ERROR: {error}") from error
