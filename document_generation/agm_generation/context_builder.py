from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from .data_provider import DataProvider
from .models import (
    ContextBuildResult,
    DocumentContext,
    FeeAllocation,
    Person,
    ValidationIssue,
)
from .text_utils import (
    clean_text,
    normalize_identity,
    normalize_statutory_clause,
    parse_date,
    parse_decimal,
)
from .template_selection import TEMPLATE_SECTION_90, classify_dwr


FYS_FIELD = "Company's current financial year start date"
FYE_FIELD = "Company's current financial year end date"
BOARD_DATE_FIELD = "Date of financial statements approved by Board of Directors"
CIRCULATION_FIELD = "Date of circulation of financial statements and reports to members"
STATUTORY_DATE_FIELD = "Date of Statutory Declaration"
DECLARANT_FIELD = "Statutory Declaration - Name of director who made declaration"
SIGNER_COUNT_FIELD = "Number of directors signing Statement by Directors"
FIRST_SIGNER_FIELD = "Name of first director who signed Statement by Directors"
SECOND_SIGNER_FIELD = "Name of second director who signed Statement by Directors"
FS_AUDITOR_FIELD = "Name of audit firm"
FEE_FIELD = "Director's remuneration - Fees (Current Financial Year)"
DWR_FIELD = "DIRECTOR WRITTEN RESOLUTION (DWR Statutory)"
MWR_FIELD = "MEMBER WRITTEN RESOLUTION (MWR Statutory)"


def _issue(issues: list[ValidationIssue], code: str, message: str, source: str) -> None:
    issues.append(ValidationIssue(code=code, message=message, source=source))


def _one_row(
    rows: list[dict],
    source: str,
    requested_company: str,
    issues: list[ValidationIssue],
) -> dict | None:
    if not rows:
        _issue(
            issues,
            "source_not_found",
            f"No record was found for {requested_company}.",
            source,
        )
        return None
    if len(rows) != 1:
        _issue(
            issues,
            "source_ambiguous",
            f"Expected one record for {requested_company}, found {len(rows)}.",
            source,
        )
        return None
    return rows[0]


def _extract_people(row: dict, prefix: str) -> list[Person]:
    people: list[Person] = []
    for index in range(1, 100):
        name_key = f"{prefix}{index} Name"
        if name_key not in row:
            break
        name = clean_text(row.get(name_key))
        if not name:
            continue
        if prefix == "Director":
            people.append(
                Person(
                    index=index,
                    name=name,
                    gender=clean_text(row.get(f"Director{index} Gender")),
                    address=clean_text(
                        row.get(f"Director{index} Residential Address")
                    ),
                )
            )
        else:
            people.append(
                Person(
                    index=index,
                    name=name,
                    gender=clean_text(row.get(f"Member{index} Gender")),
                    address=clean_text(row.get(f"Member{index} Address")),
                    shares=parse_decimal(row.get(f"Member{index} Shares")),
                    member_type=clean_text(row.get(f"Member{index} Type")),
                )
            )
    return people


def _unique_people(
    people: list[Person],
    label: str,
    issues: list[ValidationIssue],
) -> dict[str, Person]:
    result: dict[str, Person] = {}
    for person in people:
        key = normalize_identity(person.name)
        if not key:
            _issue(
                issues,
                "invalid_person_name",
                f"{label} {person.index} has an invalid name.",
                "csai_master.db:Client_Master",
            )
            continue
        if key in result:
            _issue(
                issues,
                "duplicate_person",
                f"Duplicate {label.lower()} name: {person.name}.",
                "csai_master.db:Client_Master",
            )
            continue
        result[key] = person
    return result


def _match_director(
    name: str,
    director_map: dict[str, Person],
    field: str,
    issues: list[ValidationIssue],
) -> Person | None:
    cleaned = clean_text(name)
    if not cleaned:
        _issue(
            issues,
            "missing_fs_field",
            f"Missing required FS field: {field}.",
            "FS.db:FS",
        )
        return None
    match = director_map.get(normalize_identity(cleaned))
    if match is None:
        _issue(
            issues,
            "director_mismatch",
            f"FS value '{cleaned}' does not match a Client_Master director ({field}).",
            "FS.db:FS",
        )
        return None
    if clean_text(match.gender).upper() not in {"MALE", "FEMALE"}:
        _issue(
            issues,
            "missing_director_gender",
            f"Gender is required for director {match.name}.",
            "csai_master.db:Client_Master",
        )
    return match


def _allocate_fees(
    fee_total: Decimal,
    directors: list[Person],
    members: list[Person],
    issues: list[ValidationIssue],
) -> list[FeeAllocation]:
    if fee_total <= 0:
        return []
    director_names = {normalize_identity(person.name) for person in directors}
    eligible = [
        member
        for member in members
        if normalize_identity(member.name) in director_names
    ]
    if not eligible:
        _issue(
            issues,
            "no_fee_recipients",
            "No Client_Master member matches a Client_Master director.",
            "csai_master.db:Client_Master",
        )
        return []
    for member in eligible:
        if member.shares is None or member.shares <= 0:
            _issue(
                issues,
                "invalid_fee_shares",
                f"Positive shares are required for director-member {member.name}.",
                "csai_master.db:Client_Master",
            )
    if issues:
        return []
    total_shares = sum((member.shares or Decimal("0")) for member in eligible)
    if total_shares <= 0:
        _issue(
            issues,
            "invalid_eligible_share_total",
            "Eligible director-member shares must total more than zero.",
            "csai_master.db:Client_Master",
        )
        return []

    allocations: list[FeeAllocation] = []
    allocated = Decimal("0")
    cent = Decimal("0.01")
    for position, member in enumerate(eligible):
        shares = member.shares or Decimal("0")
        percentage = shares / total_shares
        if position == len(eligible) - 1:
            amount = fee_total - allocated
        else:
            amount = (fee_total * percentage).quantize(cent, rounding=ROUND_HALF_UP)
            allocated += amount
        allocations.append(
            FeeAllocation(
                name=member.name,
                shares=shares,
                percentage=percentage,
                amount=amount.quantize(cent, rounding=ROUND_HALF_UP),
            )
        )
    return allocations


def build_document_context(
    company_name: str,
    provider: DataProvider,
    template_family: str | None = None,
) -> ContextBuildResult:
    issues: list[ValidationIssue] = []
    requested = clean_text(company_name)
    if not requested:
        return ContextBuildResult(
            requested_company=company_name,
            issues=[
                ValidationIssue(
                    code="missing_company",
                    message="A company name is required.",
                    source="input",
                )
            ],
        )

    company = _one_row(
        provider.get_company(requested),
        "csai_master.db:Client_Master",
        requested,
        issues,
    )
    if company is None:
        return ContextBuildResult(requested_company=requested, issues=issues)

    canonical_name = clean_text(company.get("Company Name"))
    registration_no = clean_text(company.get("Reg No"))
    company_folder = clean_text(company.get("Folder")) or canonical_name
    if not canonical_name:
        _issue(
            issues,
            "missing_company_name",
            "Client_Master Company Name is blank.",
            "csai_master.db:Client_Master",
        )
    if not registration_no:
        _issue(
            issues,
            "missing_registration_no",
            "Client_Master Reg No is blank.",
            "csai_master.db:Client_Master",
        )

    financial = _one_row(
        provider.get_financial(canonical_name),
        "FS.db:FS",
        canonical_name,
        issues,
    )
    constitution = _one_row(
        provider.get_constitution(canonical_name),
        "constitutions.db:Sheet1",
        canonical_name,
        issues,
    )
    auditor = _one_row(
        provider.get_auditor(canonical_name),
        "auditors.db:Sheet1",
        canonical_name,
        issues,
    )
    if financial is None or constitution is None or auditor is None:
        return ContextBuildResult(requested_company=requested, issues=issues)

    for source_name, row in (
        ("constitutions.db:Sheet1", constitution),
        ("auditors.db:Sheet1", auditor),
    ):
        other_reg = clean_text(row.get("Reg No"))
        if other_reg and normalize_identity(other_reg) != normalize_identity(registration_no):
            _issue(
                issues,
                "registration_mismatch",
                f"Registration number '{other_reg}' does not match Client_Master '{registration_no}'.",
                source_name,
            )

    directors = _extract_people(company, "Director")
    members = _extract_people(company, "Member")
    if not directors:
        _issue(
            issues,
            "missing_directors",
            "No directors were found.",
            "csai_master.db:Client_Master",
        )
    if not members:
        _issue(
            issues,
            "missing_members",
            "No members were found.",
            "csai_master.db:Client_Master",
        )
    for member in members:
        if not clean_text(member.address):
            _issue(
                issues,
                "missing_member_address",
                f"Member address is missing for {member.name}.",
                "csai_master.db:Client_Master",
            )

    director_map = _unique_people(directors, "Director", issues)
    _unique_people(members, "Member", issues)

    financial_year_start = parse_date(financial.get(FYS_FIELD))
    fye = parse_date(financial.get(FYE_FIELD))
    board_date = parse_date(financial.get(BOARD_DATE_FIELD))
    circulation_date = parse_date(financial.get(CIRCULATION_FIELD))
    statutory_date = parse_date(financial.get(STATUTORY_DATE_FIELD))
    for field, value in (
        (FYS_FIELD, financial_year_start),
        (FYE_FIELD, fye),
        (BOARD_DATE_FIELD, board_date),
        (CIRCULATION_FIELD, circulation_date),
    ):
        if value is None:
            _issue(
                issues,
                "invalid_fs_date",
                f"Missing or invalid FS date: {field}.",
                "FS.db:FS",
            )
    if financial_year_start and fye and financial_year_start > fye:
        _issue(
            issues,
            "invalid_financial_year_range",
            "Financial year start date is after the financial year end date.",
            "FS.db:FS",
        )
    if fye and board_date and fye > board_date:
        _issue(
            issues,
            "invalid_date_order",
            "Financial year end is after the board approval date.",
            "FS.db:FS",
        )
    if board_date and circulation_date and board_date > circulation_date:
        _issue(
            issues,
            "invalid_date_order",
            "Board approval date is after the circulation date.",
            "FS.db:FS",
        )

    declarant = _match_director(
        clean_text(financial.get(DECLARANT_FIELD)),
        director_map,
        DECLARANT_FIELD,
        issues,
    )
    count_value = parse_decimal(financial.get(SIGNER_COUNT_FIELD))
    signer_count = int(count_value) if count_value is not None else 0
    if signer_count not in {1, 2}:
        _issue(
            issues,
            "invalid_signer_count",
            "Number of directors signing Statement by Directors must be 1 or 2.",
            "FS.db:FS",
        )
    signer_fields = [FIRST_SIGNER_FIELD]
    if signer_count == 2:
        signer_fields.append(SECOND_SIGNER_FIELD)
    statement_signers: list[Person] = []
    for field in signer_fields:
        signer = _match_director(
            clean_text(financial.get(field)),
            director_map,
            field,
            issues,
        )
        if signer is not None:
            statement_signers.append(signer)
    if len({normalize_identity(p.name) for p in statement_signers}) != len(
        statement_signers
    ):
        _issue(
            issues,
            "duplicate_statement_signer",
            "Statement by Directors signers must be distinct.",
            "FS.db:FS",
        )

    dwr_clause = normalize_statutory_clause(clean_text(constitution.get(DWR_FIELD)))
    mwr_clause = normalize_statutory_clause(clean_text(constitution.get(MWR_FIELD)))
    selected_family = template_family or classify_dwr(dwr_clause)
    if not dwr_clause:
        _issue(issues, "missing_dwr_clause", "DWR clause is blank.", "constitutions.db:Sheet1")
    if not mwr_clause and selected_family != TEMPLATE_SECTION_90:
        _issue(issues, "missing_mwr_clause", "MWR clause is blank.", "constitutions.db:Sheet1")

    auditor_name = clean_text(auditor.get("Auditor Name"))
    if not auditor_name:
        _issue(
            issues,
            "missing_auditor",
            "Auditor Name is blank.",
            "auditors.db:Sheet1",
        )
    fs_auditor = clean_text(financial.get(FS_AUDITOR_FIELD))
    if fs_auditor and normalize_identity(fs_auditor) != normalize_identity(auditor_name):
        _issue(
            issues,
            "auditor_mismatch",
            f"FS auditor '{fs_auditor}' does not match auditors.db '{auditor_name}'.",
            "FS.db:FS",
        )

    fee_total = Decimal("0")
    fee_allocations: list[FeeAllocation] = []
    if selected_family != TEMPLATE_SECTION_90:
        raw_fee = financial.get(FEE_FIELD)
        fee_total = parse_decimal(raw_fee)
        if clean_text(raw_fee) and fee_total is None:
            _issue(
                issues,
                "invalid_director_fee",
                "Director fee is not numeric.",
                "FS.db:FS",
            )
            fee_total = Decimal("0")
        fee_total = fee_total or Decimal("0")
        if fee_total < 0:
            _issue(
                issues,
                "invalid_director_fee",
                "Director fee cannot be negative.",
                "FS.db:FS",
            )
        fee_allocations = _allocate_fees(
            fee_total,
            directors,
            members,
            issues,
        )

    if issues or not all(
        (financial_year_start, fye, board_date, circulation_date, declarant)
    ):
        return ContextBuildResult(requested_company=requested, issues=issues)

    context = DocumentContext(
        company_name=canonical_name,
        registration_no=registration_no,
        financial_year_start=financial_year_start,
        financial_year_end=fye,
        board_approval_date=board_date,
        circulation_date=circulation_date,
        statutory_declaration_date=statutory_date,
        statutory_declarant=declarant,
        statement_signers=statement_signers,
        directors=directors,
        members=members,
        dwr_clause=dwr_clause,
        mwr_clause=mwr_clause,
        auditor_name=auditor_name,
        director_fee_total=fee_total,
        company_folder=company_folder,
        template_family=selected_family,
        fee_allocations=fee_allocations,
    )
    return ContextBuildResult(requested_company=requested, context=context)


def context_preview(context: DocumentContext) -> dict:
    return {
        "company_name": context.company_name,
        "template_family": context.template_family,
        "registration_no": context.registration_no,
        "financial_year_start": context.financial_year_start.isoformat(),
        "financial_year_end": context.financial_year_end.isoformat(),
        "financial_year_span_days": (
            context.financial_year_end - context.financial_year_start
        ).days,
        "board_approval_date": context.board_approval_date.isoformat(),
        "circulation_date": context.circulation_date.isoformat(),
        "lapse_date": (context.circulation_date + timedelta(days=28)).isoformat(),
        "statutory_declarant": context.statutory_declarant.name,
        "statement_signers": [person.name for person in context.statement_signers],
        "directors": [person.name for person in context.directors],
        "members": [person.name for person in context.members],
        "auditor_name": context.auditor_name,
        "director_fee_total": str(context.director_fee_total),
        "fee_allocations": [
            {
                "name": allocation.name,
                "shares": str(allocation.shares),
                "percentage": str(allocation.percentage),
                "amount": str(allocation.amount),
            }
            for allocation in context.fee_allocations
        ],
    }
