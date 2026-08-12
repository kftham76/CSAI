from __future__ import annotations

import re
import textwrap
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


DATE_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value).replace("\u00ad", "-")).strip()
    return "" if text.upper() in {"", "NAN", "NAT", "NONE"} else text


def has_value(value: Any) -> bool:
    return clean_text(value).upper() not in {"", "NIL", "N/A", "NONE", "-"}


def normalize_identity(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    for pattern in DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def parse_decimal(value: Any) -> Decimal | None:
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return parsed if parsed >= 0 else None


def numbered_records(row: dict, prefix: str, identity_column: str) -> list[dict]:
    records: list[dict] = []
    for index in range(1, 100):
        name_key = f"{prefix}{index} Name"
        if name_key not in row:
            break
        name = clean_text(row.get(name_key))
        if not name:
            continue
        stem = f"{prefix}{index} "
        record = {"Name": name, "_index": index}
        for key, value in row.items():
            if key.startswith(stem):
                record[key[len(stem) :]] = value
        record.setdefault(identity_column, "")
        records.append(record)
    return records


def match_person(person: dict, records: list[dict]) -> dict | None:
    identity = normalize_identity(
        person.get("Identification No") or person.get("ID No") or person.get("IC")
    )
    if identity:
        matches = [
            record
            for record in records
            if normalize_identity(
                record.get("Identification No")
                or record.get("ID No")
                or record.get("IC")
            )
            == identity
        ]
        if len(matches) == 1:
            return matches[0]
    name = normalize_identity(person.get("Name"))
    matches = [
        record for record in records if normalize_identity(record.get("Name")) == name
    ]
    return matches[0] if name and len(matches) == 1 else None


def format_date(value: date, *, uppercase: bool = False) -> str:
    result = f"{value.day} {value.strftime('%B')} {value.year}"
    return result.upper() if uppercase else result


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def format_percentage(value: Decimal | None) -> str:
    return "" if value is None else f"{value.quantize(Decimal('0.01')):.2f}"


def format_nric(value: str) -> str:
    digits = re.sub(r"\D", "", clean_text(value))
    if len(digits) == 12:
        return f"{digits[:6]}-{digits[6:8]}-{digits[8:]}"
    return clean_text(value)


def display_name(value: str) -> str:
    words: list[str] = []
    for word in clean_text(value).split():
        words.append(word.upper() if word.upper() in {"A/L", "A/P", "BIN", "BINTI"} else word.title())
    return " ".join(words)


def nationality_adjective(value: str) -> str:
    normalized = clean_text(value).upper()
    return "MALAYSIAN" if normalized in {"MALAYSIA", "MALAYSIAN"} else normalized


def normalized_address(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"(?:,\s*|\s+)MALAYSIA\s*$", "", text, flags=re.I).rstrip(" ,")
    text = text.title()
    return re.sub(r"\bNo\.\s*", "No. ", text)


def address_lines(value: str, count: int, width: int) -> tuple[str, ...]:
    lines = textwrap.wrap(
        normalized_address(value),
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if len(lines) > count:
        head = lines[: count - 1]
        head.append(" ".join(lines[count - 1 :]))
        lines = head
    return tuple(lines + [""] * (count - len(lines)))


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", clean_text(value))
    return cleaned.strip().rstrip(".") or "unnamed"
