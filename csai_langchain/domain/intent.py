from dataclasses import dataclass


@dataclass
class Intent:

    intent: str

    company: str = ""

    person: str = ""

    auditor: str = ""

    financial_year_end: str = ""

    question: str = ""

    all_records: bool = False

    company_fields: tuple = ()

    requested_fields: tuple = ()


@dataclass
class MultiIntent:

    intents: tuple

    intent: str = "multi_intent"

    company: str = ""

    question: str = ""

    all_records: bool = False
