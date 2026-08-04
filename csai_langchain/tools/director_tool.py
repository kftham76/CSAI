from csai_langchain.repositories.company_repository import (
    CompanyRepository,
)


class DirectorTool:

    def __init__(self):

        self.repo = CompanyRepository()

    def execute(self, company_name):

        return self.repo.get_directors_for_company(
            company_name
        )

    def get_all_directors(self):

        return self.repo.get_all_directors()
