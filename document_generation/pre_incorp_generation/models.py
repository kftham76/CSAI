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


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, Decimal, Path)):
        return str(value)
    return value


@dataclass(frozen=True)
class SourceCandidate:
    value: Any
    source: str
    source_date: date | None = None
    suggestion: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": _json_value(self.value),
            "source": self.source,
            "source_date": self.source_date.isoformat() if self.source_date else None,
            "suggestion": self.suggestion,
        }


@dataclass
class DraftField:
    value: Any = ""
    source: str = ""
    source_date: date | None = None
    status: str = "missing"
    candidates: list[SourceCandidate] = field(default_factory=list)

    @property
    def requires_input(self) -> bool:
        return self.status in {"missing", "conflicting", "provisional"}

    def set_user_value(self, value: Any) -> None:
        self.value = value
        self.source = "terminal input"
        self.source_date = None
        self.status = "user-supplied"

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": _json_value(self.value),
            "source": self.source,
            "source_date": self.source_date.isoformat() if self.source_date else None,
            "status": self.status,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass
class DirectorDraft:
    index: int
    roster_source: str
    roster_source_date: date | None = None
    roster_status: str = "detected"
    name: DraftField = field(default_factory=DraftField)
    id_number: DraftField = field(default_factory=DraftField)
    id_type: DraftField = field(default_factory=DraftField)
    date_of_birth: DraftField = field(default_factory=DraftField)
    nationality: DraftField = field(default_factory=DraftField)
    race: DraftField = field(default_factory=DraftField)
    residential_address: DraftField = field(default_factory=DraftField)
    service_address: DraftField = field(default_factory=DraftField)
    occupation: DraftField = field(default_factory=DraftField)
    email: DraftField = field(default_factory=DraftField)
    phone: DraftField = field(default_factory=DraftField)
    shares: DraftField = field(default_factory=DraftField)

    def fields(self) -> dict[str, DraftField]:
        return {
            "name": self.name,
            "id_number": self.id_number,
            "id_type": self.id_type,
            "date_of_birth": self.date_of_birth,
            "nationality": self.nationality,
            "race": self.race,
            "residential_address": self.residential_address,
            "service_address": self.service_address,
            "occupation": self.occupation,
            "email": self.email,
            "phone": self.phone,
            "shares": self.shares,
        }

    def required_inputs(self) -> list[str]:
        result = [name for name, value in self.fields().items() if value.requires_input]
        if self.roster_status == "provisional":
            result.insert(0, "director_roster_confirmation")
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "roster_source": self.roster_source,
            "roster_source_date": (
                self.roster_source_date.isoformat() if self.roster_source_date else None
            ),
            "roster_status": self.roster_status,
            "required_inputs": self.required_inputs(),
            "fields": {name: value.to_dict() for name, value in self.fields().items()},
        }


@dataclass
class PreIncorpDraft:
    requested_company: str
    company_name: DraftField = field(default_factory=DraftField)
    registration_no: DraftField = field(default_factory=DraftField)
    incorporation_date: DraftField = field(default_factory=DraftField)
    directors: list[DirectorDraft] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    def required_inputs(self) -> list[str]:
        result: list[str] = []
        if self.incorporation_date.requires_input:
            result.append("incorporation_date")
        for director in self.directors:
            result.extend(
                f"director[{director.index}].{name}"
                for name in director.required_inputs()
            )
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_company": self.requested_company,
            "company_name": self.company_name.to_dict(),
            "registration_no": self.registration_no.to_dict(),
            "incorporation_date": self.incorporation_date.to_dict(),
            "detected_director_count": len(self.directors),
            "directors": [director.to_dict() for director in self.directors],
            "required_inputs": self.required_inputs(),
            "issues": [asdict(issue) for issue in self.issues],
        }


@dataclass
class PreparationResult:
    requested_company: str
    draft: PreIncorpDraft | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.draft is not None and not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_company": self.requested_company,
            "status": "prepared" if self.found else "invalid",
            "draft": self.draft.to_dict() if self.draft else None,
            "issues": [asdict(issue) for issue in self.issues],
        }


@dataclass(frozen=True)
class DirectorContext:
    index: int
    name: str
    id_number: str
    id_type: str
    date_of_birth: date
    nationality: str
    race: str
    residential_address: str
    service_address: str
    occupation: str
    email: str
    phone: str
    shares: Decimal


@dataclass(frozen=True)
class PreIncorpContext:
    company_name: str
    registration_no: str
    incorporation_date: date
    declaration_date: date
    directors: tuple[DirectorContext, ...]


@dataclass
class ContextBuildResult:
    requested_company: str
    context: PreIncorpContext | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.context is not None and not self.issues


@dataclass
class PreIncorpGenerationResult:
    company: str
    status: str
    output_paths: list[Path] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    preview: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["output_paths"] = [str(path) for path in self.output_paths]
        return result
