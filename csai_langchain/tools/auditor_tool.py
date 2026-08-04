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

    def get_companies_by_financial_year_end(
        self,
        financial_year_end
    ):

        return (
            self.repo
            .get_companies_by_financial_year_end(
                financial_year_end
            )
        )

    def get_all_company_records(self):

        return self.repo.get_all_company_records()

    def get_company_information(
        self,
        company_name,
        fields,
    ):

        return self.repo.get_company_information(
            company_name,
            fields,
        )

    def get_all_company_information(self, fields):

        return self.repo.get_all_company_information(fields)

    def get_distinct_auditors(self):

        return self.repo.get_distinct_auditors()
