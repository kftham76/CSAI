from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    source: str = ""


@dataclass(frozen=True)
class PersonContext:
    index: int
    role: str
    name: str
    id_type: str
    id_number: str
    nationality: str
    citizenship: str
    race: str
    gender: str
    date_of_birth: date
    passport_expiry: date | None
    residential_address: str
    email: str
    phone: str
    occupation: str
    shares: Decimal | None = None
    share_class: str = ""
    price_per_share: Decimal | None = None
    direct_percentage: Decimal | None = None
    beneficial_owner: bool = False
    becoming_bo_date: date | None = None
    control_by_other_means: bool = False


@dataclass(frozen=True)
class NewIncorpContext:
    company_name: str
    registration_no: str
    incorporation_date: date
    registered_address: str
    business_address: str
    directors: tuple[PersonContext, ...]
    members: tuple[PersonContext, ...]
    total_subscriber_shares: Decimal

    @property
    def document_count(self) -> int:
        return 8 + len(self.directors) + (2 * len(self.members))


@dataclass
class PreparationResult:
    requested_company: str
    context: NewIncorpContext | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.context is not None and not self.issues

    @property
    def status(self) -> str:
        return "valid" if self.valid else "invalid"

    @property
    def preview(self) -> dict[str, Any] | None:
        if self.context is None:
            return None
        return {
            "company_name": self.context.company_name,
            "registration_no": self.context.registration_no,
            "incorporation_date": self.context.incorporation_date.isoformat(),
            "directors": [person.name for person in self.context.directors],
            "members": [person.name for person in self.context.members],
            "document_count": self.context.document_count,
        }


@dataclass
class NewIncorpGenerationResult:
    company: str
    status: str
    output_paths: list[Path] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    preview: dict[str, Any] | None = None

    @property
    def document_count(self) -> int:
        return len(self.output_paths)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["output_paths"] = [str(path) for path in self.output_paths]
        value["document_count"] = self.document_count
        return value
