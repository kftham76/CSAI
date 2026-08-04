import re
from dataclasses import dataclass


CLIENT_SOURCE = "csai_master.db:Client_Master"
AUDITOR_SOURCE = "auditors.db:Sheet1"
EBOS_SOURCE = "ebos_master.db:EBOS_Master"
CONSTITUTION_SOURCE = "constitutions.db:Sheet1"

DWR_FIELD = (
    "DIRECTOR WRITTEN RESOLUTION (DWR Statutory)"
)
MWR_FIELD = (
    "MEMBER WRITTEN RESOLUTION (MWR Statutory)"
)


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
}
