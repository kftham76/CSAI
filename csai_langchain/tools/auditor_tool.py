from csai_langchain.repositories.auditor_repository import (
    AuditorRepository,
)


class AuditorTool:

    def __init__(self):

        self.repo = AuditorRepository()

    def execute(
        self,
        company_name
    ):

        return self.get_auditor_for_company(
            company_name
        )

    def get_auditor_for_company(
        self,
        company_name
    ):

        return self.repo.get_auditor_for_company(
            company_name
        )

    def get_companies_by_auditor(
        self,
        auditor_name
    ):

        return self.repo.get_companies_by_auditor(
            auditor_name
        )

    def get_distinct_auditors(self):

        return self.repo.get_distinct_auditors()
