import pandas as pd

from csai_langchain.repositories.company_repository import CompanyRepository


class ShareholderTool:

    def __init__(self):
        self.repo = CompanyRepository()

    def execute(self, company_name):

        company = self.repo.get_company(company_name)

        if not company:
            return []

        row = company[0]

        shareholders = []

        for i in range(1, 51):

            key = f"Member{i} Name"

            if key not in row:
                break

            name = row.get(key)

            if pd.isna(name):
                continue

            name = str(name).strip()

            if not name:
                continue

            shareholders.append({

                "Type":
                    row.get(f"Member{i} Type"),

                "Name":
                    name,

                "ID Type":
                    row.get(f"Member{i} ID Type"),

                "ID No":
                    row.get(f"Member{i} ID No"),

                "Nationality":
                    row.get(f"Member{i} Nationality"),

                "Race":
                    row.get(f"Member{i} Race"),

                "Gender":
                    row.get(f"Member{i} Gender"),

                "DOB":
                    row.get(f"Member{i} DOB"),

                "Address":
                    row.get(f"Member{i} Address"),

                "Shares":
                    row.get(f"Member{i} Shares"),

                "Share Type":
                    row.get(f"Member{i} Share Type")
            })

        return shareholders