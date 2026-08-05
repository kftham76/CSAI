from csai_langchain.repositories.financial_statement_repository import (
    FinancialStatementRepository,
)


class FinancialStatementTool:

    def __init__(self):
        self.repo = FinancialStatementRepository()

    def get_company_information(self, company_name, fields):
        return self.repo.get_company_information(company_name, fields)

    def get_all_company_information(self, fields):
        return self.repo.get_all_company_information(fields)
