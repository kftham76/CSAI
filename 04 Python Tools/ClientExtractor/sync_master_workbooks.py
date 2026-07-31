"""Synchronize the master Excel workbooks to their runtime SQLite tables."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sqlite3

import pandas as pd


DB_DIR = Path(
    os.environ.get(
        "CSAI_DB_DIR",
        r"C:\CSAI_OS\04 Python Tools\DB",
    )
)


@dataclass(frozen=True)
class WorkbookTarget:
    source: Path
    sheet: str
    database: Path
    table: str
    required_columns: tuple[str, ...]


TARGETS = (
    WorkbookTarget(
        source=Path(
            r"D:\CSAI_DATA\Database\clients_master.xlsx"
        ),
        sheet="Sheet1",
        database=DB_DIR / "csai_master.db",
        table="Client_Master",
        required_columns=(
            "Company Name",
            "Reg No",
            "Director1 Name",
            "Member1 Name",
            "UpdatedAt",
        ),
    ),
    WorkbookTarget(
        source=Path(
            r"D:\CSAI_DATA\Database\Ebos data.xlsx"
        ),
        sheet="EBOS Data",
        database=DB_DIR / "ebos_master.db",
        table="EBOS_Master",
        required_columns=(
            "Company",
            "Company Name",
            "Company No",
            "Company Status",
            "BO1 Source PDF",
            "BO1 Name",
            "UpdatedAt",
        ),
    ),
)


def read_workbook(target):
    """Read and validate one workbook while preserving source text."""

    if not target.source.is_file():
        raise FileNotFoundError(
            f"Workbook was not found: {target.source}"
        )

    with pd.ExcelFile(target.source) as workbook:
        if target.sheet not in workbook.sheet_names:
            raise ValueError(
                f"Sheet '{target.sheet}' was not found in "
                f"{target.source}. Available sheets: "
                f"{', '.join(workbook.sheet_names)}"
            )

        frame = pd.read_excel(
            workbook,
            sheet_name=target.sheet,
            dtype=str,
            keep_default_na=False,
        )

    columns = list(frame.columns)

    if not columns or any(
        not str(column).strip()
        for column in columns
    ):
        raise ValueError(
            f"{target.source} contains a blank column heading."
        )

    duplicate_columns = sorted({
        str(column)
        for column in columns
        if columns.count(column) > 1
    })

    if duplicate_columns:
        raise ValueError(
            f"{target.source} contains duplicate columns: "
            f"{', '.join(duplicate_columns)}"
        )

    missing_columns = [
        column
        for column in target.required_columns
        if column not in frame.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{target.source} is missing required columns: "
            f"{', '.join(missing_columns)}"
        )

    # Keep all nonblank source values as text and store Excel blanks
    # as SQL NULL.
    for column in frame.columns:
        frame[column] = frame[column].map(
            lambda value: (
                None
                if (
                    value is None
                    or pd.isna(value)
                    or str(value).strip() == ""
                )
                else str(value)
            )
        )

    return frame


def replace_table_atomic(frame, target):
    """Replace one SQLite table atomically while preserving other tables."""

    target.database.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = target.database.with_name(
        f".{target.database.stem}.sync.tmp.db"
    )

    if temp_path.exists():
        temp_path.unlink()

    if target.database.exists():
        shutil.copy2(
            target.database,
            temp_path,
        )

    try:
        connection = sqlite3.connect(
            str(temp_path)
        )

        try:
            with connection:
                frame.to_sql(
                    target.table,
                    connection,
                    if_exists="replace",
                    index=False,
                )

            imported_columns = [
                row[1]
                for row in connection.execute(
                    f"PRAGMA table_info([{target.table}])"
                )
            ]
            imported_rows = connection.execute(
                f"SELECT COUNT(*) FROM [{target.table}]"
            ).fetchone()[0]

            if imported_columns != list(frame.columns):
                raise RuntimeError(
                    f"Column validation failed for {target.table}."
                )

            if imported_rows != len(frame):
                raise RuntimeError(
                    f"Row-count validation failed for {target.table}: "
                    f"expected {len(frame)}, imported {imported_rows}."
                )

        finally:
            connection.close()

        try:
            os.replace(
                temp_path,
                target.database,
            )
        except PermissionError:
            # Windows prevents replacing a database file while another
            # process has it open. Fall back to an atomic table rename
            # inside the live database so readers can remain connected.
            replace_table_transactional(
                frame,
                target,
            )

    finally:
        if temp_path.exists():
            temp_path.unlink()


def replace_table_transactional(
    frame,
    target,
):
    """Atomically swap a validated staging table inside a locked database."""

    staging_table = (
        f"__sync_{target.table}"
    )
    connection = sqlite3.connect(
        str(target.database),
        timeout=30,
    )

    try:
        connection.execute(
            f"DROP TABLE IF EXISTS [{staging_table}]"
        )
        connection.commit()

        frame.to_sql(
            staging_table,
            connection,
            if_exists="replace",
            index=False,
        )

        staging_columns = [
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info([{staging_table}])"
            )
        ]
        staging_rows = connection.execute(
            f"SELECT COUNT(*) FROM [{staging_table}]"
        ).fetchone()[0]

        if staging_columns != list(frame.columns):
            raise RuntimeError(
                f"Staging-column validation failed for "
                f"{target.table}."
            )

        if staging_rows != len(frame):
            raise RuntimeError(
                f"Staging row-count validation failed for "
                f"{target.table}: expected {len(frame)}, "
                f"imported {staging_rows}."
            )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )
            connection.execute(
                f"DROP TABLE IF EXISTS [{target.table}]"
            )
            connection.execute(
                f"ALTER TABLE [{staging_table}] "
                f"RENAME TO [{target.table}]"
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    finally:
        try:
            connection.execute(
                f"DROP TABLE IF EXISTS [{staging_table}]"
            )
            connection.commit()
        finally:
            connection.close()


def synchronize(target):
    """Synchronize and report one workbook/database mapping."""

    frame = read_workbook(target)
    replace_table_atomic(
        frame,
        target,
    )

    print(f"Source      : {target.source}")
    print(f"Sheet       : {target.sheet}")
    print(f"Destination : {target.database}")
    print(f"Table       : {target.table}")
    print(f"Rows        : {len(frame)}")
    print(f"Columns     : {len(frame.columns)}")
    print()


def main():
    for target in TARGETS:
        synchronize(target)


if __name__ == "__main__":
    main()
