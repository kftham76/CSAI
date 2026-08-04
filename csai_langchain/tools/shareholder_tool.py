from csai_langchain.repositories.company_repository import (
    CompanyRepository,
)


class ShareholderTool:

    def __init__(self):

        self.repo = CompanyRepository()

    def execute(self, company_name):

        return self.repo.get_shareholders_for_company(
            company_name
        )

    def get_all_shareholders(self):

        return self.repo.get_all_shareholders()
