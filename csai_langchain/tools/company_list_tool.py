from csai_langchain.repositories.company_repository import (
    CompanyRepository,
)


class CompanyListTool:

    def __init__(self):

        self.repo = CompanyRepository()

    def get_all_company_names(self):

        return self.repo.get_all_company_names()

    def get_all_company_records(self):

        return self.repo.get_all_companies()

    def get_company_records(self, company_name):

        return self.repo.get_company(
            company_name
        )

    def get_all_annual_return_dates(self):

        return self.repo.get_all_annual_return_dates()

    def get_annual_return_date(self, company_name):

        return self.repo.get_annual_return_date(
            company_name
        )

    def get_all_company_information(self, fields):

        return self.repo.get_all_company_information(
            fields
        )

    def get_company_information(
        self,
        company_name,
        fields
    ):

        return self.repo.get_company_information(
            company_name,
            fields
        )

    def get_all_extraction_issues(self):

        return self.repo.get_all_extraction_issues()

    def get_extraction_issues_for_company(
        self,
        company_name
    ):

        return self.repo.get_extraction_issues_for_company(
            company_name
        )

    def get_all_statutory_documents(self):

        return self.repo.get_all_statutory_documents()

    def get_statutory_documents_for_company(
        self,
        company_name
    ):

        return self.repo.get_statutory_documents_for_company(
            company_name
        )

    def get_all_statutory_events(self):

        return self.repo.get_all_statutory_events()

    def get_statutory_events_for_company(
        self,
        company_name
    ):

        return self.repo.get_statutory_events_for_company(
            company_name
        )
