from dataclasses import dataclass


@dataclass
class Intent:

    intent: str

    company: str = ""

    person: str = ""

    question: str = ""