import re
import sqlite3
import pandas as pd

from csai_langchain_modify.config.settings import CLIENT_DB


class CompanyRepository:

    def __init__(self):

        self.db = CLIENT_DB

    def _normalize(self, name):

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

    def get_company(self, company_name):

        conn = sqlite3.connect(self.db)

        df = pd.read_sql(
            "SELECT * FROM Client_Master",
            conn
        )

        conn.close()

        if df.empty:
            return []

        df["search_name"] = (
            df["Company Name"]
            .fillna("")
            .apply(self._normalize)
        )

        target = self._normalize(company_name)

        result = df[
            df["search_name"].str.contains(
                target,
                case=False,
                na=False
            )
        ]

        return result.to_dict(
            orient="records"
        )

    def get_all_companies(self):

        conn = sqlite3.connect(self.db)

        df = pd.read_sql(
            "SELECT * FROM Client_Master",
            conn
        )

        conn.close()

        return df.to_dict(
            orient="records"
        )


    def get_person_directorship(self, person_name):

        person = self._normalize(person_name)

        companies = self.get_all_companies()

        results = []

        for row in companies:

            for i in range(1, 50):

                key = f"Director{i} Name"

                if key not in row:
                    break

                name = row.get(key)

                if pd.isna(name):
                    continue

                if self._normalize(str(name)) == person:

                    results.append({

                        "Company Name":
                            row.get("Company Name"),

                        "Reg No":
                            row.get("Reg No")
                    })

                    break

        return results

print("CompanyRepository loaded from:", __file__)