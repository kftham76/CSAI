from __future__ import annotations

from datetime import timedelta

from .data_provider import DataProvider
from .models import (
    ContextBuildResult,
    DirectorContext,
    PreIncorpContext,
    PreIncorpDraft,
    ValidationIssue,
)
from .preparation import prepare_pre_incorp_generation
from .value_utils import (
    clean_text,
    identification_type_code,
    normalize_identity,
    parse_date,
    parse_shares,
)


DIRECTOR_FIELD_LABELS = {
    "name": "Name",
    "id_number": "IC",
    "id_type": "ID Type",
    "date_of_birth": "DOB",
    "nationality": "Nationality",
    "race": "Race",
    "residential_address": "Residential Address",
    "service_address": "Service Address",
    "occupation": "Business Occupation",
    "email": "Email",
    "phone": "Contact No",
    "shares": "matching Member Shares",
}


def context_from_draft(draft: PreIncorpDraft) -> ContextBuildResult:
    issues = list(draft.issues)
    company_name = clean_text(draft.company_name.value)
    registration_no = clean_text(draft.registration_no.value)
    incorporation_date = parse_date(draft.incorporation_date.value)
    if not company_name:
        issues.append(
            ValidationIssue(
                "missing_company_name",
                "Company name is required.",
                draft.company_name.source or "terminal input",
            )
        )
    if incorporation_date is None:
        issues.append(
            ValidationIssue(
                "missing_incorporation_date",
                "Incorporation date is missing or invalid.",
                draft.incorporation_date.source or "terminal input",
            )
        )

    directors: list[DirectorContext] = []
    seen: set[str] = set()
    for index, director in enumerate(draft.directors, start=1):
        values = {
            name: clean_text(field.value)
            for name, field in director.fields().items()
            if name not in {"date_of_birth", "shares"}
        }
        dob = parse_date(director.date_of_birth.value)
        shares = parse_shares(director.shares.value)
        missing = [
            DIRECTOR_FIELD_LABELS[name]
            for name, value in values.items()
            if not value
        ]
        if dob is None:
            missing.append(DIRECTOR_FIELD_LABELS["date_of_birth"])
        if shares is None:
            missing.append(DIRECTOR_FIELD_LABELS["shares"])
        if values.get("id_type") and not identification_type_code(values["id_type"]):
            missing.append("recognized ID Type")
        if missing:
            display_name = values.get("name") or f"Director {index}"
            issues.append(
                ValidationIssue(
                    "missing_director_data",
                    f"{display_name} is missing required pre-incorporation data: "
                    f"{', '.join(dict.fromkeys(missing))}.",
                    "hybrid draft",
                )
            )
            continue

        identity = normalize_identity(values["id_number"]) or normalize_identity(values["name"])
        if not identity or identity in seen:
            issues.append(
                ValidationIssue(
                    "duplicate_director",
                    f"Duplicate or invalid director: {values.get('name') or index}.",
                    "hybrid draft",
                )
            )
            continue
        seen.add(identity)
        directors.append(
            DirectorContext(
                index=index,
                name=values["name"],
                id_number=values["id_number"],
                id_type=values["id_type"],
                date_of_birth=dob,
                nationality=values["nationality"],
                race=values["race"],
                residential_address=values["residential_address"],
                service_address=values["service_address"],
                occupation=values["occupation"],
                email=values["email"],
                phone=values["phone"],
                shares=shares,
            )
        )

    if not draft.directors:
        issues.append(
            ValidationIssue(
                "missing_directors",
                "No directors were confirmed for the company.",
                "hybrid draft",
            )
        )
    if issues or incorporation_date is None or not company_name:
        return ContextBuildResult(requested_company=draft.requested_company, issues=issues)

    return ContextBuildResult(
        requested_company=draft.requested_company,
        context=PreIncorpContext(
            company_name=company_name,
            registration_no=registration_no,
            incorporation_date=incorporation_date,
            declaration_date=incorporation_date - timedelta(days=1),
            directors=tuple(directors),
        ),
    )


def build_pre_incorp_context(
    requested_company: str,
    provider: DataProvider,
) -> ContextBuildResult:
    prepared = prepare_pre_incorp_generation(requested_company, provider)
    if prepared.draft is None:
        return ContextBuildResult(requested_company=requested_company, issues=prepared.issues)
    return context_from_draft(prepared.draft)


def context_preview(context: PreIncorpContext) -> dict:
    return {
        "company_name": context.company_name,
        "registration_no": context.registration_no,
        "incorporation_date": context.incorporation_date.isoformat(),
        "declaration_date": context.declaration_date.isoformat(),
        "directors": [director.name for director in context.directors],
        "document_count": len(context.directors) * 2,
    }


__all__ = [
    "build_pre_incorp_context",
    "clean_text",
    "context_from_draft",
    "context_preview",
    "normalize_identity",
    "parse_date",
    "parse_shares",
]
