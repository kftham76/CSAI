from dataclasses import dataclass


@dataclass
class Intent:

    intent: str

    company: str = ""

    person: str = ""

    auditor: str = ""

    question: str = ""
