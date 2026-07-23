import pandas as pd

from csai_langchain_modify.repositories.company_repository import CompanyRepository


class DirectorTool:

    def __init__(self):
        self.repo = CompanyRepository()

    def execute(self, company_name):

        company = self.repo.get_company(company_name)

        if not company:
            return []

        row = company[0]

        directors = []

        for i in range(1, 50):

            key = f"Director{i} Name"

            if key not in row:
                break

            name = row.get(key)

            if pd.isna(name):
                continue

            name = str(name).strip()

            if not name:
                continue

            directors.append({

                "Name": name,

                "IC": row.get(f"Director{i} IC"),

                "DOB": row.get(f"Director{i} DOB"),

                "Nationality": row.get(f"Director{i} Nationality"),

                "Residential Address":
                    row.get(f"Director{i} Residential Address")
            })

        return directors