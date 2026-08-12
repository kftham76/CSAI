from __future__ import annotations

from pathlib import Path
from typing import Protocol

from csai_langchain.repositories.new_incorp_repository import NewIncorpRepository


NEW_INCORP_DATABASE = Path(r"C:\CSAI_OS\06 Data\databases\new_incorp.db")


class DataProvider(Protocol):
    def get_company(self, company_name: str) -> list[dict]: ...


class CsaiNewIncorpDataProvider:
    """Read-only adapter over the existing CSAI New_Incorp repository."""

    def __init__(self) -> None:
        self.repository = NewIncorpRepository()
        if self.repository.db.resolve() != NEW_INCORP_DATABASE.resolve():
            raise RuntimeError(
                "New-incorporation retrieval is restricted to "
                f"{NEW_INCORP_DATABASE}."
            )

    def get_company(self, company_name: str) -> list[dict]:
        return self.repository.get_company(company_name)
