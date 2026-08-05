import re
from dataclasses import dataclass


CLIENT_SOURCE = "csai_master.db:Client_Master"
AUDITOR_SOURCE = "auditors.db:Sheet1"
EBOS_SOURCE = "ebos_master.db:EBOS_Master"
CONSTITUTION_SOURCE = "constitutions.db:Sheet1"
FS_SOURCE = "FS.db:FS"

DWR_FIELD = (
    "DIRECTOR WRITTEN RESOLUTION (DWR Statutory)"
)
MWR_FIELD = (
    "MEMBER WRITTEN RESOLUTION (MWR Statutory)"
)

FS_CURRENT_START_FIELD = (
    "Company's current financial year start date"
)
FS_CURRENT_END_FIELD = (
    "Company's current financial year end date"
)
FS_BOARD_APPROVAL_FIELD = (
    "Date of financial statements approved by Board of Directors"
)
FS_CIRCULATION_FIELD = (
    "Date of circulation of financial statements and reports to members"
)
FS_STATUTORY_DATE_FIELD = "Date of Statutory Declaration"
FS_DECLARANT_FIELD = (
    "Statutory Declaration - Name of director who made declaration"
)
FS_SIGNER_COUNT_FIELD = (
    "Number of directors signing Statement by Directors"
)
FS_FIRST_SIGNER_FIELD = (
    "Name of first director who signed Statement by Directors"
)
FS_SECOND_SIGNER_FIELD = (
    "Name of second director who signed Statement by Directors"
)
FS_AUDIT_FIRM_FIELD = "Name of audit firm"
FS_DIRECTOR_FEE_FIELD = (
    "Director's remuneration - Fees (Current Financial Year)"
)
FS_SOURCE_PDF_FIELD = "Source PDF"


@dataclass(frozen=True)
class Capability:

    group: str
    intent: str
    requested_field: str
    source: str
    patterns: tuple


CAPABILITIES = (
    Capability(
        group="company_information",
        intent="company_information",
        requested_field="Annual Return Date",
        source=CLIENT_SOURCE,
        patterns=(
            re.compile(
                r"\bann?ual\s+ret(?:ur|ru)ns?\b",
                re.I,
            ),
            re.compile(r"\bar\s+dates?\b", re.I),
        ),
    ),
    Capability(
        group="auditor_information",
        intent="auditor_information",
        requested_field="Financial Year End",
        source=AUDITOR_SOURCE,
        patterns=(
            re.compile(
                r"\bfinancial(?:\s*-\s*|\s+)"
                r"year(?:\s*-\s*|\s+)end\b",
                re.I,
            ),
            re.compile(r"\bfye\b", re.I),
        ),
    ),
    Capability(
        group="auditor_information",
        intent="auditor_information",
        requested_field="Auditor Name",
        source=AUDITOR_SOURCE,
        patterns=(
            re.compile(r"\bauditors?\b", re.I),
            re.compile(
                r"\baudit(?:ing)?\s+firms?\b",
                re.I,
            ),
            re.compile(r"\bwho\s+audits\b", re.I),
        ),
    ),
    Capability(
        group="director",
        intent="director",
        requested_field="Directors",
        source=CLIENT_SOURCE,
        patterns=(
            re.compile(
                r"\bdirectors?\b"
                r"(?!\s+written\s+resolution)",
                re.I,
            ),
        ),
    ),
    Capability(
        group="shareholder",
        intent="shareholder",
        requested_field="Shareholders",
        source=CLIENT_SOURCE,
        patterns=(
            re.compile(r"\bshareholders?\b", re.I),
            re.compile(r"\bshareholding\b", re.I),
            re.compile(
                r"\bmembers?\b"
                r"(?!\s+written\s+resolution)",
                re.I,
            ),
        ),
    ),
    Capability(
        group="beneficial_owner",
        intent="beneficial_owner",
        requested_field="Beneficial Owners",
        source=EBOS_SOURCE,
        patterns=(
            re.compile(
                r"\bbeneficial\s+owners?\b",
                re.I,
            ),
            re.compile(
                r"\bbeneficial\s+ownership\b",
                re.I,
            ),
            re.compile(r"\bebos?\b", re.I),
            re.compile(r"\bbo\b", re.I),
        ),
    ),
    Capability(
        group="constitution_information",
        intent="constitution_information",
        requested_field=DWR_FIELD,
        source=CONSTITUTION_SOURCE,
        patterns=(
            re.compile(
                r"\bdirectors?['’]?\s+written\s+"
                r"resolutions?\b",
                re.I,
            ),
            re.compile(r"\bdwr\b", re.I),
            re.compile(r"\bconstitutions?\b", re.I),
        ),
    ),
    Capability(
        group="constitution_information",
        intent="constitution_information",
        requested_field=MWR_FIELD,
        source=CONSTITUTION_SOURCE,
        patterns=(
            re.compile(
                r"\bmembers?['’]?\s+written\s+"
                r"resolutions?\b",
                re.I,
            ),
            re.compile(r"\bmwr\b", re.I),
            re.compile(r"\bconstitutions?\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_CURRENT_START_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\b(?:company['\u2019]?s\s+)?current\s+financial\s+"
                r"year\s+start\s+date\b",
                re.I,
            ),
            re.compile(r"\bcurrent\s+financial\s+year\s+start\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_CURRENT_END_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\b(?:company['\u2019]?s\s+)?current\s+financial\s+"
                r"year\s+end\s+date\b",
                re.I,
            ),
            re.compile(r"\bcurrent\s+fye\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_BOARD_APPROVAL_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\b(?:date\s+of\s+)?financial\s+statements?\s+"
                r"approved\s+by\s+(?:the\s+)?board"
                r"(?:\s+of\s+directors)?\b",
                re.I,
            ),
            re.compile(r"\bboard\s+approval\s+date\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_CIRCULATION_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\bdate\s+of\s+circulation\s+of\s+financial\s+"
                r"statements?(?:\s+and\s+reports?)?\b",
                re.I,
            ),
            re.compile(r"\bfinancial\s+statements?\s+circulation\s+date\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_STATUTORY_DATE_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(r"\bdate\s+of\s+statutory\s+declaration\b", re.I),
            re.compile(r"\bstatutory\s+declaration\s+date\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_DECLARANT_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\bname\s+of\s+(?:the\s+)?director\s+who\s+made\s+"
                r"(?:the\s+)?(?:statutory\s+)?declaration\b",
                re.I,
            ),
            re.compile(r"\bstatutory\s+declarant\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_SIGNER_COUNT_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\bnumber\s+of\s+directors?\s+signing\s+"
                r"(?:the\s+)?statement\s+by\s+directors\b",
                re.I,
            ),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_FIRST_SIGNER_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\bname\s+of\s+(?:the\s+)?first\s+director\s+who\s+"
                r"signed\s+(?:the\s+)?statement\s+by\s+directors\b",
                re.I,
            ),
            re.compile(r"\bfirst\s+statement\s+by\s+directors\s+signer\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_SECOND_SIGNER_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\bname\s+of\s+(?:the\s+)?second\s+director\s+who\s+"
                r"signed\s+(?:the\s+)?statement\s+by\s+directors\b",
                re.I,
            ),
            re.compile(r"\bsecond\s+statement\s+by\s+directors\s+signer\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_AUDIT_FIRM_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(r"\bname\s+of\s+(?:the\s+)?audit\s+firm\b", re.I),
            re.compile(r"\bfinancial\s+statements?\s+audit\s+firm\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_DIRECTOR_FEE_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(
                r"\bdirectors?['\u2019]?s?\s+remuneration\s*[-:]?\s*fees?\b",
                re.I,
            ),
            re.compile(r"\bcurrent\s+year\s+directors?['\u2019]?s?\s+fees?\b", re.I),
        ),
    ),
    Capability(
        group="financial_statement_information",
        intent="financial_statement_information",
        requested_field=FS_SOURCE_PDF_FIELD,
        source=FS_SOURCE,
        patterns=(
            re.compile(r"\bfinancial\s+statements?\s+source\s+pdf\b", re.I),
            re.compile(r"\bfs\s+source\s+pdf\b", re.I),
        ),
    ),
)


INTENT_SOURCES = {
    "company_information": CLIENT_SOURCE,
    "director": CLIENT_SOURCE,
    "director_list": CLIENT_SOURCE,
    "shareholder": CLIENT_SOURCE,
    "shareholder_list": CLIENT_SOURCE,
    "beneficial_owner": EBOS_SOURCE,
    "beneficial_owner_list": EBOS_SOURCE,
    "auditor_information": AUDITOR_SOURCE,
    "constitution_information": CONSTITUTION_SOURCE,
    "financial_statement_information": FS_SOURCE,
}
