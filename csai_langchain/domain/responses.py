from dataclasses import dataclass, field


@dataclass
class SearchResult:

    status: str

    intent: str

    answer: str = ""

    company: str = ""

    person: str = ""

    auditor: str = ""

    financial_year_end: str = ""

    count: int = 0

    results: list = field(default_factory=list)

    sources: list = field(default_factory=list)


@dataclass
class SearchSection:

    intent: str

    requested_fields: list = field(default_factory=list)

    status: str = "not_found"

    answer: str = ""

    count: int = 0

    results: list = field(default_factory=list)

    sources: list = field(default_factory=list)


@dataclass
class MultiSearchResult:

    status: str

    intent: str = "multi_intent"

    answer: str = ""

    company: str = ""

    count: int = 0

    section_count: int = 0

    sections: list = field(default_factory=list)

    sources: list = field(default_factory=list)
