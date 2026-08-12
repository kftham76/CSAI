from __future__ import annotations

import re
import textwrap
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "nat", "none"}:
        return ""
    return re.sub(r"\s+", " ", text)


def normalize_identity(value: Any) -> str:
    text = clean_text(value).upper().replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(text[:10], pattern).date()
        except ValueError:
            continue
    return None


def parse_decimal(value: Any) -> Decimal | None:
    text = clean_text(value).replace(",", "").replace("RM", "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def format_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def format_currency(value: Decimal) -> str:
    return f"RM{value:,.2f}"


def display_person_name(value: str) -> str:
    words = []
    for word in clean_text(value).split():
        if word.upper() in {"@", "A/L", "A/P", "BIN", "BINTI"}:
            words.append(word.upper())
        else:
            words.append(word.title())
    return " ".join(words)


def honorific(gender: str) -> str:
    normalized = clean_text(gender).upper()
    if normalized == "MALE":
        return "Mr."
    if normalized == "FEMALE":
        return "Ms."
    return ""


def honorific_name(name: str, gender: str) -> str:
    prefix = honorific(gender)
    shown = display_person_name(name)
    return f"{prefix} {shown}".strip()


def normalize_statutory_clause(value: str) -> str:
    text = clean_text(value)
    text = (
        text.replace("â€™", "'")
        .replace("â€˜", "'")
        .replace("�", "'")
        .replace("’", "'")
        .replace("‘", "'")
    )
    text = re.sub(
        r"\bCOMPANY'S\s+ACT\b",
        "COMPANIES ACT",
        text,
        flags=re.IGNORECASE,
    )
    return text


def normalize_address(value: str, width: int = 38) -> str:
    text = clean_text(value)
    text = re.sub(
        r"(?:,\s*|\s+)MALAYSIA\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).rstrip(" ,")
    text = text.title()
    text = re.sub(r"\bNo\.\s*", "No. ", text)
    lines = textwrap.wrap(
        text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return "\n".join(lines)


def safe_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]', "-", clean_text(value))
    return value.rstrip(". ")
