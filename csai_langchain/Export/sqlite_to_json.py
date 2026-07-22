from pathlib import Path
import sqlite3
import pandas as pd
import json

ROOT = Path(__file__).resolve().parents[2]

DB_FOLDER = ROOT / "04 Python Tools" / "DB"
JSON_FOLDER = ROOT / "06_LangChain" / "data_json"

JSON_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


def export_db(db_path):

    db_name = db_path.stem

    print(f"\nProcessing {db_name}")

    output_folder = JSON_FOLDER / db_name
    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    conn = sqlite3.connect(db_path)

    tables = pd.read_sql(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        """,
        conn
    )

    for table in tables["name"]:

        print(f"  Exporting {table}")

        df = pd.read_sql(
            f"SELECT * FROM [{table}]",
            conn
        )

        output_file = (
            output_folder /
            f"{table}.json"
        )

        df.to_json(
            output_file,
            orient="records",
            force_ascii=False,
            indent=4
        )

    conn.close()


def main():

    db_files = list(
        DB_FOLDER.glob("*.db")
    )

    for db in db_files:
        export_db(db)

    print("\nDone")


if __name__ == "__main__":
    main()