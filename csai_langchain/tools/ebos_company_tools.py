import sqlite3
import pandas as pd
import re

DB = r"C:\CSAI_OS\04 Python Tools\DB\ebos_master.db"


def normalize(text):

    if not text:
        return ""

    text = text.upper()

    text = (
        text
        .replace(".", "")
        .replace(",", "")
        .replace("&", "AND")
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def get_ebos_company(company_name):

    conn = sqlite3.connect(DB)

    df = pd.read_sql(
        """
        SELECT *
        FROM EBOS_Master
        """,
        conn
    )

    conn.close()

    company_std = normalize(
        company_name
    )

    df["company_std"] = (

        df["Company Name"]
        .fillna("")
        .apply(normalize)

    )

    df = df[
        df["company_std"]
        .str.contains(
            company_std,
            na=False
        )
    ]

    return df.to_dict(
        orient="records"
    )