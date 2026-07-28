from csai_langchain.repositories.ebos_repository import EBOSRepository


class BeneficialOwnerTool:

    def __init__(self):
        self.repo = EBOSRepository()

    def execute(self, company_name):

        rows = self.repo.get_current_beneficial_owners(
    company_name
)

        if not rows:
            return []

        results = []

        for row in rows:

            results.append({

                "Name": row.get("Name"),

                "IC": row.get("IC"),

                "Nationality": row.get("Nationality"),

                "Designation": row.get("Designation"),

                "BO Status": row.get("BO Status"),

                "Direct Ownership %":
                    row.get("Criteria A - Direct Ownership %"),

                "Voting Shares %":
                    row.get("Criteria B - Voting Shares %"),

                "Date of Becoming BO":
                    row.get("Date of Becoming BO"),

                "Date of Cessation":
                    row.get("Date of Cessation")
            })

        return results