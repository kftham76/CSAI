from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from .data_provider import CsaiNewIncorpDataProvider, DataProvider
from .models import (
    NewIncorpContext,
    PersonContext,
    PreparationResult,
    ValidationIssue,
)
from .value_utils import (
    clean_text,
    has_value,
    match_person,
    nationality_adjective,
    normalize_identity,
    numbered_records,
    parse_date,
    parse_decimal,
)


SOURCE = "new_incorp.db:New_Incorp"
S14_SOURCE = f"{SOURCE}/S14"
CURRENT_SOURCE = f"{SOURCE}/current"


def _check_capacity(value: str, label: str, maximum: int, issues: list[ValidationIssue]) -> None:
    if len(clean_text(value)) > maximum:
        issues.append(
            ValidationIssue(
                "field_over_capacity",
                f"{label} exceeds the template capacity of {maximum} characters.",
                S14_SOURCE,
            )
        )


def _check_roster_conflicts(records: list[dict], role: str, issues: list[ValidationIssue]) -> None:
    identities: dict[str, str] = {}
    names: dict[str, str] = {}
    for record in records:
        name = normalize_identity(record.get("Name"))
        identity = normalize_identity(
            record.get("Identification No") or record.get("ID No") or record.get("IC")
        )
        if identity in identities:
            issues.append(ValidationIssue("conflicting_person_data", f"Duplicate {role} identity: {identity}", CURRENT_SOURCE))
        elif identity:
            identities[identity] = name
        if name in names and names[name] != identity:
            issues.append(ValidationIssue("conflicting_person_data", f"Conflicting {role} identities for {record.get('Name')}", CURRENT_SOURCE))
        elif name:
            names[name] = identity


def _check_cross_roster_conflicts(directors: list[dict], members: list[dict], issues: list[ValidationIssue]) -> None:
    director_ids = {
        normalize_identity(record.get("Identification No") or record.get("ID No") or record.get("IC")):
        normalize_identity(record.get("Name"))
        for record in directors
    }
    director_names = {
        normalize_identity(record.get("Name")):
        normalize_identity(record.get("Identification No") or record.get("ID No") or record.get("IC"))
        for record in directors
    }
    for member in members:
        member_id = normalize_identity(
            member.get("Identification No") or member.get("ID No") or member.get("IC")
        )
        member_name = normalize_identity(member.get("Name"))
        if member_id and member_id in director_ids and director_ids[member_id] != member_name:
            issues.append(ValidationIssue("conflicting_person_data", f"Director/member names conflict for identity {member_id}", CURRENT_SOURCE))
        if member_name and member_name in director_names and director_names[member_name] != member_id:
            issues.append(ValidationIssue("conflicting_person_data", f"Director/member identities conflict for {member.get('Name')}", CURRENT_SOURCE))


def _first_value(candidates: list[tuple[dict | None, tuple[str, ...]]]) -> Any:
    for record, keys in candidates:
        if not record:
            continue
        for key in keys:
            value = record.get(key)
            if has_value(value):
                return value
    return ""


def _active_bo(person: dict, records: list[dict], incorporation_date: date) -> dict | None:
    matched = match_person(person, records)
    if not matched:
        return None
    becoming = parse_date(matched.get("Date of Becoming BO"))
    cessation = parse_date(matched.get("Date of Cessation"))
    if becoming and becoming > incorporation_date:
        return None
    if cessation and cessation <= incorporation_date:
        return None
    return matched


def _required_person_fields(role: str) -> tuple[tuple[str, str], ...]:
    fields = (
        ("name", "Name"),
        ("id_type", "ID Type"),
        ("id_number", "Identification No."),
        ("nationality", "Nationality"),
        ("race", "Race"),
        ("gender", "Gender"),
        ("date_of_birth", "Date of Birth"),
        ("residential_address", "Residential Address"),
        ("email", "Email"),
        ("phone", "Contact No."),
        ("occupation", "Business Occupation"),
    )
    if role == "member":
        return fields + (("shares", "Shares"), ("share_class", "Share Type"))
    return fields


def _build_person(
    role: str,
    record: dict,
    counterpart: dict | None,
    active_bo: dict | None,
    current_primary: dict | None,
    current_secondary: dict | None,
    incorporation_date: date,
    total_shares: Decimal | None,
    issues: list[ValidationIssue],
) -> PersonContext | None:
    name = clean_text(record.get("Name"))
    id_type = clean_text(record.get("ID Type"))
    id_number = clean_text(
        record.get("Identification No") or record.get("ID No") or record.get("IC")
    )
    nationality = nationality_adjective(
        _first_value(
            [
                (record, ("Nationality",)),
                (counterpart, ("Nationality",)),
                (active_bo, ("Nationality",)),
                (current_primary, ("Nationality",)),
                (current_secondary, ("Nationality",)),
            ]
        )
    )
    citizenship = nationality_adjective(
        _first_value(
            [
                (active_bo, ("Citizenship",)),
                (current_primary, ("Citizenship",)),
                (current_secondary, ("Citizenship",)),
                ({"Nationality": nationality}, ("Nationality",)),
            ]
        )
    )
    race = clean_text(
        _first_value(
            [
                (record, ("Race",)),
                (counterpart, ("Race",)),
                (active_bo, ("Race",)),
                (current_primary, ("Race",)),
                (current_secondary, ("Race",)),
            ]
        )
    ).upper()
    gender = clean_text(
        _first_value(
            [
                (record, ("Gender",)),
                (counterpart, ("Gender",)),
                (active_bo, ("Gender",)),
                (current_primary, ("Gender",)),
                (current_secondary, ("Gender",)),
            ]
        )
    ).upper()
    dob = parse_date(
        _first_value(
            [
                (record, ("DOB",)),
                (counterpart, ("DOB",)),
                (active_bo, ("DOB",)),
                (current_primary, ("DOB",)),
                (current_secondary, ("DOB",)),
            ]
        )
    )
    passport_expiry = parse_date(
        _first_value(
            [
                (record, ("Passport Expiry",)),
                (counterpart, ("Passport Expiry",)),
                (current_primary, ("Passport Expiry",)),
                (current_secondary, ("Passport Expiry",)),
            ]
        )
    )
    address = clean_text(
        _first_value(
            [
                (record, ("Address", "Residential Address")),
                (counterpart, ("Address",)),
                (active_bo, ("Residential Address",)),
                (current_primary, ("Residential Address", "Address")),
                (current_secondary, ("Residential Address", "Address")),
            ]
        )
    )
    email = clean_text(
        _first_value(
            [
                (record, ("Email",)),
                (counterpart, ("Email",)),
                (active_bo, ("Email",)),
                (current_primary, ("Email",)),
                (current_secondary, ("Email",)),
            ]
        )
    )
    phone = clean_text(
        _first_value(
            [
                (record, ("Contact No",)),
                (counterpart, ("Contact No",)),
                (active_bo, ("Contact No",)),
                (current_primary, ("Contact No",)),
                (current_secondary, ("Contact No",)),
            ]
        )
    )
    occupation = clean_text(
        _first_value(
            [
                (record, ("Business Occupation", "Designation")),
                (counterpart, ("Business Occupation", "Designation")),
                (active_bo, ("Designation",)),
                (current_primary, ("Business Occupation", "Designation")),
                (current_secondary, ("Business Occupation", "Designation")),
            ]
        )
    ).upper()

    shares = parse_decimal(record.get("Shares")) if role == "member" else None
    share_class = clean_text(record.get("Share Type")) if role == "member" else ""
    price = parse_decimal(record.get("Price per Share")) if role == "member" else None
    percentage: Decimal | None = None
    if role == "member" and shares is not None and total_shares and total_shares > 0:
        percentage = shares * Decimal("100") / total_shares
    criteria_c = clean_text((active_bo or {}).get("Criteria C"))
    control = has_value(criteria_c)
    beneficial_owner = bool(
        role == "member"
        and ((percentage is not None and percentage >= Decimal("20")) or control)
    )
    becoming_date = (
        parse_date((active_bo or {}).get("Date of Becoming BO"))
        or (incorporation_date if beneficial_owner else None)
    )

    values = {
        "name": name,
        "id_type": id_type,
        "id_number": id_number,
        "nationality": nationality,
        "race": race,
        "gender": gender,
        "date_of_birth": dob,
        "residential_address": address,
        "email": email,
        "phone": phone,
        "occupation": occupation,
        "shares": shares,
        "share_class": share_class,
    }
    missing = [label for field, label in _required_person_fields(role) if not values[field]]
    if "PASSPORT" in id_type.upper() and passport_expiry is None:
        missing.append("Passport Expiry Date")
    if missing:
        issues.append(
            ValidationIssue(
                "missing_person_data",
                f"{name or role.title()} is missing required {role} data: {', '.join(missing)}.",
                CURRENT_SOURCE,
            )
        )
        return None

    for value, label, maximum in (
        (name, "Name", 80),
        (id_number, "Identification No.", 40),
        (nationality, "Nationality", 40),
        (race, "Race", 30),
        (gender, "Gender", 20),
        (address, "Residential Address", 180),
        (email, "Email", 100),
        (phone, "Contact No.", 40),
        (occupation, "Business Occupation", 80),
    ):
        _check_capacity(value, f"{name} {label}", maximum, issues)

    return PersonContext(
        index=int(record.get("_index") or 0),
        role=role,
        name=name,
        id_type=id_type,
        id_number=id_number,
        nationality=nationality,
        citizenship=citizenship,
        race=race,
        gender=gender,
        date_of_birth=dob,
        passport_expiry=passport_expiry,
        residential_address=address,
        email=email,
        phone=phone,
        occupation=occupation,
        shares=shares,
        share_class=share_class,
        price_per_share=price,
        direct_percentage=percentage,
        beneficial_owner=beneficial_owner,
        becoming_bo_date=becoming_date,
        control_by_other_means=control,
    )


def prepare_new_incorp_generation(
    company_name: str,
    provider: DataProvider | None = None,
) -> PreparationResult:
    data_provider = provider or CsaiNewIncorpDataProvider()
    rows = data_provider.get_company(company_name)
    if not rows:
        return PreparationResult(
            requested_company=company_name,
            issues=[ValidationIssue("source_not_found", f"No New_Incorp record was found for {company_name}.", SOURCE)],
        )
    if len(rows) != 1:
        return PreparationResult(
            requested_company=company_name,
            issues=[ValidationIssue("source_ambiguous", f"Expected one New_Incorp row for {company_name}, found {len(rows)}.", SOURCE)],
        )

    row = rows[0]
    issues: list[ValidationIssue] = []
    canonical = clean_text(row.get("Company Name"))
    registration = clean_text(row.get("Reg No"))
    incorporation_date = parse_date(row.get("S14 Incorporation Date"))
    registered_address = clean_text(row.get("S14 Registered Address"))
    business_address = clean_text(row.get("S14 Business Address"))
    for value, label in (
        (canonical, "Company Name"),
        (registration, "Reg No"),
        (incorporation_date, "S14 Incorporation Date"),
        (registered_address, "S14 Registered Address"),
        (business_address, "S14 Business Address"),
    ):
        if not value:
            issues.append(ValidationIssue("missing_company_data", f"{label} is required.", S14_SOURCE))
    for value, label, maximum in (
        (canonical, "Company Name", 100),
        (registration, "Reg No", 50),
        (registered_address, "S14 Registered Address", 180),
        (business_address, "S14 Business Address", 180),
    ):
        _check_capacity(value, label, maximum, issues)
    if incorporation_date is None:
        return PreparationResult(company_name, issues=issues)

    current_directors = numbered_records(row, "Director", "IC")
    current_members = numbered_records(row, "Member", "ID No")
    _check_roster_conflicts(current_directors, "director", issues)
    _check_roster_conflicts(current_members, "member", issues)
    _check_cross_roster_conflicts(current_directors, current_members, issues)
    bo_records = numbered_records(row, "BO", "Identification No")
    if not current_directors:
        issues.append(ValidationIssue("missing_directors", "No current directors were found.", CURRENT_SOURCE))
    if not current_members:
        issues.append(ValidationIssue("missing_members", "No current members were found.", CURRENT_SOURCE))
    corporate = [
        member.get("Name", "")
        for member in current_members
        if "COMPANY" in clean_text(member.get("Type") or member.get("ID Type")).upper()
    ]
    if corporate:
        issues.append(
            ValidationIssue(
                "unsupported_corporate_member",
                "Corporate-member templates are required for: " + ", ".join(corporate),
                CURRENT_SOURCE,
            )
        )

    total_shares = sum(
        (parse_decimal(member.get("Shares")) or Decimal("0") for member in current_members),
        Decimal("0"),
    )
    if total_shares <= 0:
        issues.append(ValidationIssue("invalid_total_shares", "Total current member shares must be greater than zero.", CURRENT_SOURCE))

    directors: list[PersonContext] = []
    for record in current_directors:
        built = _build_person(
            "director",
            record,
            match_person(record, current_members),
            _active_bo(record, bo_records, incorporation_date),
            None,
            None,
            incorporation_date,
            None,
            issues,
        )
        if built:
            directors.append(built)

    members: list[PersonContext] = []
    for record in current_members:
        if "COMPANY" in clean_text(record.get("Type") or record.get("ID Type")).upper():
            continue
        built = _build_person(
            "member",
            record,
            match_person(record, current_directors),
            _active_bo(record, bo_records, incorporation_date),
            None,
            None,
            incorporation_date,
            total_shares,
            issues,
        )
        if built:
            members.append(built)

    if issues:
        return PreparationResult(company_name, issues=issues)
    return PreparationResult(
        requested_company=company_name,
        context=NewIncorpContext(
            company_name=canonical,
            registration_no=registration,
            incorporation_date=incorporation_date,
            registered_address=registered_address,
            business_address=business_address,
            directors=tuple(directors),
            members=tuple(members),
            total_subscriber_shares=total_shares,
        ),
    )


def context_preview(context: NewIncorpContext) -> dict[str, Any]:
    return {
        "company_name": context.company_name,
        "registration_no": context.registration_no,
        "incorporation_date": context.incorporation_date.isoformat(),
        "registered_address": context.registered_address,
        "business_address": context.business_address,
        "directors": [person.name for person in context.directors],
        "members": [person.name for person in context.members],
        "total_subscriber_shares": str(context.total_subscriber_shares),
        "document_count": context.document_count,
    }
