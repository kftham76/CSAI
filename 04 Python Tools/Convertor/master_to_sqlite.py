"""Convert the client master workbook into its runtime SQLite table."""

import os
from pathlib import Path
import shutil
import sqlite3

import pandas as pd


SOURCE_FILE = Path(r"D:\CSAI_DATA\Database\clients_master.xlsx")
SHEET_NAME = "Sheet1"
DATABASE_FILE = Path(r"C:\CSAI_OS\06 Data\databases\csai_master.db")
TABLE_NAME = "Client_Master"

REQUIRED_COLUMNS = (
    "Company Name",
    "Reg No",
    "Director1 Name",
    "Member1 Name",
    "UpdatedAt",
)


def _is_identifier_column(column: str) -> bool:
    """Return whether Excel must be prevented from coercing an identifier."""
    return "IC" in column or "ID No" in column


def _is_blank(value) -> bool:
    return (
        value is None
        or pd.isna(value)
        or (isinstance(value, str) and not value.strip())
    )


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert Excel blanks to SQL NULL without flattening numeric columns."""
    frame = frame.copy()
    for column in frame.columns:
        series = frame[column]
        if pd.api.types.is_datetime64_any_dtype(series.dtype):
            frame[column] = series.map(
                lambda value: None if _is_blank(value) else value.isoformat()
            )
        elif pd.api.types.is_numeric_dtype(series.dtype):
            frame[column] = series.map(
                lambda value: None if _is_blank(value) else value
            )
        else:
            frame[column] = series.map(
                lambda value: None if _is_blank(value) else str(value)
            )
    return frame


def _expected_sqlite_types(frame: pd.DataFrame) -> list[str]:
    expected = []
    for column in frame.columns:
        dtype = frame[column].dtype
        if pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_bool_dtype(dtype):
            expected.append("INTEGER")
        elif pd.api.types.is_float_dtype(dtype):
            expected.append("REAL")
        else:
            expected.append("TEXT")
    return expected


def load_workbook() -> pd.DataFrame:
    """Read and validate the configured worksheet."""
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
                "The client master worksheet contains blank column headings "
                f"at positions: {blank_columns}"
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
                "The client master worksheet contains duplicate columns: "
                f"{', '.join(duplicate_columns)}"
            )

        identifier_types = {
            column: str
            for column in normalized_columns
            if _is_identifier_column(column)
        }
        frame = pd.read_excel(
            workbook,
            sheet_name=SHEET_NAME,
            dtype=identifier_types,
            keep_default_na=False,
        )

    actual_columns = list(frame.columns)
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in actual_columns
    ]
    if missing_columns:
        raise ValueError(
            "The client master worksheet is missing required columns: "
            f"{', '.join(missing_columns)}"
        )

    return _normalize_frame(frame)


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
    expected_types = _expected_sqlite_types(expected)
    if imported_types != expected_types:
        raise RuntimeError(
            f"Column-type validation failed for {table_name}: "
            f"expected {expected_types}, imported {imported_types}."
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
    """Replace Client_Master atomically while preserving other tables."""
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
