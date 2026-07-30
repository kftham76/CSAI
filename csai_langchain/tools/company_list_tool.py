from csai_langchain.repositories.company_repository import (
    CompanyRepository,
)


class CompanyListTool:

    def __init__(self):

        self.repo = CompanyRepository()

    def get_all_company_names(self):

        return self.repo.get_all_company_names()
