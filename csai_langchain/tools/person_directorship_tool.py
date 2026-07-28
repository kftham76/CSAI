from csai_langchain.repositories.company_repository import CompanyRepository


class PersonDirectorshipTool:

    def __init__(self):

        self.repo = CompanyRepository()

    def execute(self, person_name):

        return self.repo.get_person_directorship(
            person_name
        )