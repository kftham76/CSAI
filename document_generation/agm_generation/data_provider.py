from __future__ import annotations

from typing import Protocol

from csai_langchain.repositories.auditor_repository import AuditorRepository
from csai_langchain.repositories.company_repository import CompanyRepository
from csai_langchain.repositories.constitution_repository import (
    ConstitutionRepository,
)
from csai_langchain.repositories.financial_statement_repository import (
    FinancialStatementRepository,
)


class DataProvider(Protocol):
    def get_company(self, company_name: str) -> list[dict]: ...

    def get_financial(self, company_name: str) -> list[dict]: ...

    def get_constitution(self, company_name: str) -> list[dict]: ...

    def get_auditor(self, company_name: str) -> list[dict]: ...


class CsaiDataProvider:
    """Thin read-only adapter over the existing csai_langchain repositories."""

    def __init__(self) -> None:
        self.company_repository = CompanyRepository()
        self.financial_repository = FinancialStatementRepository()
        self.constitution_repository = ConstitutionRepository()
        self.auditor_repository = AuditorRepository()

    def get_company(self, company_name: str) -> list[dict]:
        return self.company_repository.get_company(company_name)

    def get_financial(self, company_name: str) -> list[dict]:
        return self.financial_repository.get_company_information(
            company_name,
            self.financial_repository.REQUIRED_COLUMNS,
        )

    def get_constitution(self, company_name: str) -> list[dict]:
        return self.constitution_repository.get_company_information(
            company_name,
            [
                "DIRECTOR WRITTEN RESOLUTION (DWR Statutory)",
                "MEMBER WRITTEN RESOLUTION (MWR Statutory)",
            ],
        )

    def get_auditor(self, company_name: str) -> list[dict]:
        return self.auditor_repository.get_auditor_for_company(company_name)
