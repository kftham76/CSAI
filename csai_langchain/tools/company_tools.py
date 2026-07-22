import re
import sqlite3
import pandas as pd

DB = r"C:\CSAI_OS\04 Python Tools\DB\csai_master.db"


def normalize_company(name):

    if not name:
        return ""

    name = name.upper()

    name = re.sub(
        r"[.,]",
        "",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name.strip()


def get_company(company_name):

    conn = sqlite3.connect(DB)

    df = pd.read_sql(
        """
        SELECT *
        FROM Client_Master
        """,
        conn
    )

    conn.close()

    if df.empty:
        return []

    df["search_name"] = (
        df["Company Name"]
        .fillna("")
        .apply(normalize_company)
    )

    target = normalize_company(
        company_name
    )

    df = df[
        df["search_name"]
        .str.contains(
            target,
            case=False,
            na=False
        )
    ]

    return df.to_dict(
        orient="records"
    )

def get_all_companies():

    conn = sqlite3.connect(DB)

    df = pd.read_sql(
        """
        SELECT *
        FROM Client_Master
        """,
        conn
    )

    conn.close()

    return df.to_dict(
        orient="records"
    )