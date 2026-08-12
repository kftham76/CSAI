from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Person:
    index: int
    name: str
    gender: str = ""
    address: str = ""
    shares: Decimal | None = None
    member_type: str = ""


@dataclass(frozen=True)
class FeeAllocation:
    name: str
    shares: Decimal
    percentage: Decimal
    amount: Decimal


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    source: str = ""


@dataclass(frozen=True)
class Section90Details:
    agm_ordinal: str
    meeting_date: date
    notice_date: date
    letter_date: date
    venue_lines: tuple[str, ...]
    meeting_start_time: str
    meeting_end_time: str
    retiring_directors: list[Person]
    rotation_workbook_path: Path


@dataclass
class DocumentContext:
    company_name: str
    registration_no: str
    financial_year_start: date
    financial_year_end: date
    board_approval_date: date
    circulation_date: date
    statutory_declaration_date: date | None
    statutory_declarant: Person
    statement_signers: list[Person]
    directors: list[Person]
    members: list[Person]
    dwr_clause: str
    mwr_clause: str
    auditor_name: str
    director_fee_total: Decimal
    company_folder: str = ""
    template_family: str = "standard"
    section90: Section90Details | None = None
    fee_allocations: list[FeeAllocation] = field(default_factory=list)

    @property
    def has_director_fee(self) -> bool:
        return self.director_fee_total > 0


@dataclass
class ContextBuildResult:
    requested_company: str
    context: DocumentContext | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.context is not None and not self.issues


@dataclass
class GenerationResult:
    company: str
    status: str
    output_path: Path | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    preview: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["output_path"] = str(self.output_path) if self.output_path else None
        return result
