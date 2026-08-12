from __future__ import annotations

from typing import Protocol

from csai_langchain.repositories.new_incorp_repository import (
    NewIncorpRepository,
)


class DataProvider(Protocol):
    def get_company(self, company_name: str) -> list[dict]: ...


class CsaiPreIncorpDataProvider:
    """Read-only adapter over the CSAI new-incorporation repository."""

    def __init__(self) -> None:
        self.new_incorp_repository = NewIncorpRepository()

    def get_company(self, company_name: str) -> list[dict]:
        return self.new_incorp_repository.get_company(company_name)
