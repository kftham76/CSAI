from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def clean_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00ad", "-")).strip()


def normalize_identity(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    for pattern in (
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def parse_shares(value) -> Decimal | None:
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        shares = Decimal(text)
    except InvalidOperation:
        return None
    return shares if shares >= 0 else None


def has_value(value) -> bool:
    return clean_text(value).upper() not in {"", "NIL", "N/A", "NONE", "NAN", "-"}


def looks_like_email(value) -> bool:
    text = clean_text(value)
    return "@" in text and "." in text.rsplit("@", 1)[-1]


def identification_type_code(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())
    if normalized in {"MYKAD", "NRIC", "BLUEIC", "B"}:
        return "B"
    if normalized in {"PASSPORT", "P"}:
        return "P"
    if normalized in {"REDIC", "R"}:
        return "R"
    if normalized in {"MILITARYID", "MILITARY", "Z"}:
        return "Z"
    if normalized in {"POLICEID", "POLICE", "M"}:
        return "M"
    return ""
