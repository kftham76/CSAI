from dataclasses import dataclass, field


@dataclass
class SearchResult:

    status: str

    intent: str

    answer: str = ""

    company: str = ""

    person: str = ""

    auditor: str = ""

    count: int = 0

    results: list = field(default_factory=list)

    sources: list = field(default_factory=list)
