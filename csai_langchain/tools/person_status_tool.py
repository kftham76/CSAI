from csai_langchain.repositories.company_repository import (
    CompanyRepository,
)
from csai_langchain.repositories.ebos_repository import (
    EBOSRepository,
)


class PersonStatusTool:

    def __init__(self):

        self.company_repo = CompanyRepository()
        self.ebos_repo = EBOSRepository()

    def get_beneficial_ownership_history(
        self,
        person_name
    ):

        return (
            self.ebos_repo
            .get_person_beneficial_ownership_history(
                person_name
            )
        )

    def get_shareholdings(
        self,
        person_name
    ):

        return (
            self.company_repo
            .get_person_shareholdings(
                person_name
            )
        )

    def get_company_associations(
        self,
        person_name
    ):

        return (
            self.company_repo
            .get_person_company_associations(
                person_name
            )
        )

    def get_combined_status(
        self,
        person_name
    ):

        results = []

        for row in (
            self.company_repo
            .get_person_directorship(
                person_name
            )
        ):
            results.append({
                "Role": "Director",
                "Status": "Current",
                "Name": person_name,
                **row,
            })

        for row in (
            self.get_beneficial_ownership_history(
                person_name
            )
        ):
            results.append({
                "Role": "Beneficial Owner",
                **row,
            })

        for row in self.get_shareholdings(
            person_name
        ):
            results.append({
                "Role": "Shareholder",
                **row,
            })

        return results
