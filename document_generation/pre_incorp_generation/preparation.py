from __future__ import annotations

from datetime import date
from typing import Any

from .data_provider import CsaiPreIncorpDataProvider, DataProvider
from .models import (
    DirectorDraft,
    DraftField,
    PreparationResult,
    PreIncorpDraft,
    SourceCandidate,
    ValidationIssue,
)
from .value_utils import (
    clean_text,
    has_value,
    identification_type_code,
    normalize_identity,
    parse_date,
    parse_shares,
)


NEW_INCORP_SOURCE = "new_incorp.db:New_Incorp"
CURRENT_SOURCE = f"{NEW_INCORP_SOURCE}/Current"
S14_SOURCE = f"{NEW_INCORP_SOURCE}/S14"
EBOS_SOURCE = f"{NEW_INCORP_SOURCE}/EBOS"


def _field(
    value: Any = "",
    source: str = "",
    source_date: date | None = None,
    status: str | None = None,
) -> DraftField:
    present = value is not None and (not isinstance(value, str) or has_value(value))
    return DraftField(
        value=value if present else "",
        source=source if present else "",
        source_date=source_date if present else None,
        status=status or ("detected" if present else "missing"),
    )


def _candidate_key(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    parsed_date = parse_date(value)
    if parsed_date is not None:
        return parsed_date.isoformat()
    return normalize_identity(value)


def _add_candidate(field: DraftField, candidate: SourceCandidate) -> None:
    key = _candidate_key(candidate.value)
    if not key:
        return
    if any(_candidate_key(existing.value) == key for existing in field.candidates):
        return
    field.candidates.append(candidate)


def _person_identity(record: dict) -> str:
    return normalize_identity(
        record.get("IC")
        or record.get("ID No")
        or record.get("Identification No")
    )


def _numbered_records(row: dict, prefix: str, identity_column: str) -> list[dict]:
    result: list[dict] = []
    for index in range(1, 100):
        name_key = f"{prefix}{index} Name"
        if name_key not in row:
            break
        name = clean_text(row.get(name_key))
        if not name:
            continue
        record = {"Name": name, "_index": index}
        stem = f"{prefix}{index} "
        for key, value in row.items():
            if key.startswith(stem):
                record[key[len(stem) :]] = value
        if identity_column not in record:
            record[identity_column] = ""
        result.append(record)
    return result


def _unique_person_match(person: dict, records: list[dict]) -> dict | None:
    identity = _person_identity(person)
    if identity:
        matches = [
            record
            for record in records
            if _person_identity(record) == identity
        ]
        if len(matches) == 1:
            return matches[0]
    name = normalize_identity(person.get("Name"))
    matches = [record for record in records if normalize_identity(record.get("Name")) == name]
    return matches[0] if name and len(matches) == 1 else None


def _director_event_match(person: dict, event: dict) -> bool:
    identity = _person_identity(person)
    event_identity = _person_identity(event)
    if identity and event_identity:
        return identity == event_identity
    return bool(
        normalize_identity(person.get("Name"))
        and normalize_identity(person.get("Name")) == normalize_identity(event.get("Name"))
    )


def _events_for_person(person: dict, events: list[dict]) -> list[dict]:
    identity = _person_identity(person)
    if identity:
        return [event for event in events if _director_event_match(person, event)]
    name = normalize_identity(person.get("Name"))
    matches = [
        event for event in events if name and normalize_identity(event.get("Name")) == name
    ]
    identities = {
        _person_identity(event) or normalize_identity(event.get("Name"))
        for event in matches
    }
    identities.discard("")
    return matches if len(identities) == 1 else []


def _event_source_date(event: dict) -> date | None:
    parsed = parse_date(event.get("_source_date"))
    if parsed is not None:
        return parsed
    for column in (
        "Received DateTime",
        "Date Received",
        "Date of Application",
        "Date of Data Recorded",
    ):
        parsed = parse_date(event.get(column))
        if parsed is not None:
            return parsed
    return None


def _event_rank(event: dict, incorporation_date: date | None) -> tuple:
    source_date = _event_source_date(event)
    becoming_date = parse_date(event.get("Date of Becoming BO"))
    exact_becoming = incorporation_date is not None and becoming_date == incorporation_date
    if incorporation_date is None or source_date is None:
        distance = 10**9
        before = 1
    else:
        distance = abs((source_date - incorporation_date).days)
        before = 1 if source_date < incorporation_date else 0
    return (
        0 if exact_becoming else 1,
        distance,
        before,
        source_date or date.max,
        clean_text(event.get("Submission No")),
    )


def _event_candidates(
    events: list[dict],
    column: str,
    incorporation_date: date | None,
    *,
    suggestion: bool = False,
) -> list[SourceCandidate]:
    unique: dict[str, SourceCandidate] = {}
    for event in sorted(events, key=lambda value: _event_rank(value, incorporation_date)):
        value = clean_text(event.get(column))
        if not has_value(value):
            continue
        key = _candidate_key(value)
        unique.setdefault(
            key,
            SourceCandidate(
                value=value,
                source=EBOS_SOURCE,
                source_date=_event_source_date(event),
                suggestion=suggestion,
            ),
        )
    return list(unique.values())


def _apply_ebos(
    field: DraftField,
    candidates: list[SourceCandidate],
) -> None:
    if not candidates or _candidate_key(field.value):
        return
    for candidate in candidates:
        _add_candidate(field, candidate)
    selected = candidates[0]
    field.value = selected.value
    field.source = selected.source
    field.source_date = selected.source_date
    field.status = "detected"


def _suggest(field: DraftField, candidates: list[SourceCandidate]) -> None:
    if field.value not in (None, ""):
        return
    for candidate in candidates:
        _add_candidate(field, candidate)


def _current_director_fields(record: dict) -> dict[str, Any]:
    return {
        "name": record.get("Name"),
        "id_number": record.get("IC"),
        "id_type": record.get("ID Type"),
        "date_of_birth": parse_date(record.get("DOB")),
        "nationality": record.get("Nationality"),
        "race": record.get("Race"),
        "residential_address": record.get("Residential Address"),
        "service_address": record.get("Service Address"),
        "occupation": record.get("Business Occupation"),
        "email": record.get("Email"),
        "phone": record.get("Contact No"),
    }


def _make_director(
    index: int,
    person: dict,
    current_member: dict | None,
    events: list[dict],
    incorporation_date: date | None,
) -> DirectorDraft:
    values = _current_director_fields(person)
    draft = DirectorDraft(
        index=index,
        roster_source=CURRENT_SOURCE,
        roster_status="detected",
    )
    for name, value in values.items():
        setattr(draft, name, _field(value, CURRENT_SOURCE))

    current_shares = parse_shares((current_member or {}).get("Shares"))
    draft.shares = _field(current_shares, CURRENT_SOURCE)

    for field_name, ebos_column in (
        ("date_of_birth", "DOB"),
        ("nationality", "Nationality"),
        ("race", "Race"),
        ("residential_address", "Residential Address"),
        ("email", "Email"),
        ("phone", "Contact No"),
    ):
        _apply_ebos(
            getattr(draft, field_name),
            _event_candidates(events, ebos_column, incorporation_date),
        )

    _suggest(
        draft.service_address,
        _event_candidates(events, "Business Address", incorporation_date, suggestion=True),
    )
    _suggest(
        draft.occupation,
        _event_candidates(events, "Designation", incorporation_date, suggestion=True),
    )

    if draft.id_type.value and not identification_type_code(str(draft.id_type.value)):
        draft.id_type.status = "provisional"
    return draft


def prepare_pre_incorp_generation(
    company_name: str,
    provider: DataProvider | None = None,
) -> PreparationResult:
    data_provider = provider or CsaiPreIncorpDataProvider()
    rows = data_provider.get_company(company_name)
    if not rows:
        return PreparationResult(
            requested_company=company_name,
            issues=[
                ValidationIssue(
                    "source_not_found",
                    f"No New_Incorp record was found for {company_name}.",
                    NEW_INCORP_SOURCE,
                )
            ],
        )
    if len(rows) != 1:
        return PreparationResult(
            requested_company=company_name,
            issues=[
                ValidationIssue(
                    "source_ambiguous",
                    f"Expected one New_Incorp record for {company_name}, found {len(rows)}.",
                    NEW_INCORP_SOURCE,
                )
            ],
        )

    row = rows[0]
    canonical_name = clean_text(row.get("Company Name"))
    current_incorporation_date = parse_date(row.get("Incorporate Date"))
    s14_incorporation_date = parse_date(row.get("S14 Incorporation Date"))
    if current_incorporation_date:
        incorporation_field = _field(
            current_incorporation_date,
            CURRENT_SOURCE,
        )
    elif s14_incorporation_date:
        incorporation_field = _field(
            s14_incorporation_date,
            S14_SOURCE,
            s14_incorporation_date,
        )
    else:
        incorporation_field = _field()

    draft = PreIncorpDraft(
        requested_company=company_name,
        company_name=_field(canonical_name, NEW_INCORP_SOURCE),
        registration_no=_field(row.get("Reg No"), NEW_INCORP_SOURCE),
        incorporation_date=incorporation_field,
    )
    if not canonical_name:
        draft.issues.append(
            ValidationIssue(
                "missing_company_name",
                "New_Incorp Company Name is blank.",
                NEW_INCORP_SOURCE,
            )
        )
        return PreparationResult(company_name, draft=draft)

    incorporation_date = parse_date(draft.incorporation_date.value)
    current_directors = _numbered_records(row, "Director", "IC")
    current_members = _numbered_records(row, "Member", "ID No")
    roster = current_directors
    ebos_events = _numbered_records(row, "BO", "Identification No")
    ebos_source_date = (
        parse_date(row.get("EBOS Received DateTime"))
        or parse_date(row.get("EBOS Date Received"))
        or parse_date(row.get("EBOS Selected DateTime"))
    )
    for event in ebos_events:
        event["_source_date"] = ebos_source_date
        event["Submission No"] = row.get("EBOS Submission Number")

    for index, person in enumerate(roster, start=1):
        current_member = _unique_person_match(person, current_members)
        person_events = _events_for_person(person, ebos_events)
        draft.directors.append(
            _make_director(
                index,
                person,
                current_member,
                person_events,
                incorporation_date,
            )
        )

    if not draft.directors:
        draft.issues.append(
            ValidationIssue(
                "missing_directors",
                "No current directors were found for the company.",
                NEW_INCORP_SOURCE,
            )
        )
    return PreparationResult(requested_company=company_name, draft=draft)
