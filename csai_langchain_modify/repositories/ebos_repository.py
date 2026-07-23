import sqlite3
import pandas as pd

from csai_langchain_modify.config.settings import EBOS_DB


class EBOSRepository:

    def __init__(self):
        self.db = EBOS_DB

    def get_current_beneficial_owners(self, company_name):

        conn = sqlite3.connect(self.db)

        df = pd.read_sql(
            "SELECT * FROM EBOS_Master",
            conn
        )

        conn.close()

        if df.empty:
            return []

        ####################################################
        # Normalize Company Name
        ####################################################

        df["search_name"] = (
            df["Company Name"]
            .fillna("")
            .str.upper()
            .str.replace(".", "", regex=False)
            .str.strip()
        )

        target = (
            company_name.upper()
            .replace(".", "")
            .strip()
        )

        ####################################################
        # Filter Company
        ####################################################

        df = df[
            df["search_name"].str.contains(
                target,
                case=False,
                na=False
            )
        ]

        if df.empty:
            return []

        ####################################################
        # Keep Latest Records
        ####################################################

        df["UpdatedAt"] = pd.to_datetime(
            df["UpdatedAt"],
            errors="coerce"
        )

        df = df.sort_values(
            "UpdatedAt",
            ascending=False
        )

        ####################################################
        # Remove Historical Records
        ####################################################

        df = df.drop_duplicates(
            subset=[
                "Company Name",
                "Name",
                "IC"
            ],
            keep="first"
        )

        ####################################################
        # Remove Cessation Records
        ####################################################

        df = df[
            df["BO Status"]
            .fillna("")
            .str.upper() != "CESSATION"
        ]

        ####################################################
        # Return
        ####################################################

        return df.to_dict(
            orient="records"
        )