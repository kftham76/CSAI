from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

from .models import PreIncorpDraft
from .value_utils import clean_text


Input = Callable[[str], str]
Output = Callable[[str], None]


FIELD_LABELS = {
    "director_roster_confirmation": "Director roster confirmation",
    "name": "Name",
    "id_number": "IC / passport number",
    "id_type": "ID type",
    "date_of_birth": "Date of birth",
    "nationality": "Nationality",
    "race": "Race",
    "residential_address": "Residential address",
    "service_address": "Service address",
    "occupation": "Business occupation",
    "email": "Email",
    "phone": "Contact number",
    "shares": "Shares",
}


def _display_value(value) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, Decimal):
        return format(value, "f")
    return clean_text(value) or "<missing>"


def display_draft(draft: PreIncorpDraft, output: Output = print) -> None:
    output("")
    output(f"Company: {_display_value(draft.company_name.value)}")
    output(f"Registration No.: {_display_value(draft.registration_no.value)}")
    output(
        "Incorporation Date: "
        f"{_display_value(draft.incorporation_date.value)} "
        f"[{draft.incorporation_date.status}; "
        f"{draft.incorporation_date.source or 'no source'}]"
    )
    output(f"Detected {len(draft.directors)} current director(s):")
    for director in draft.directors:
        required = [
            FIELD_LABELS.get(name, name)
            for name in director.required_inputs()
        ]
        missing = ", ".join(required) if required else "none"
        output(
            f"  {director.index}. {_display_value(director.name.value)} | "
            f"ID: {_display_value(director.id_number.value)} | "
            f"Shares: {_display_value(director.shares.value)} | "
            f"Roster: {director.roster_source} ({director.roster_status}) | "
            f"Needs review: {missing}"
        )


def complete_interactively(
    draft: PreIncorpDraft,
    reference_no: str | None,
    input_func: Input = input,
    output: Output = print,
) -> tuple[str, str]:
    """Display retrieved data and prompt only for a missing Reference No."""

    display_draft(draft, output)
    reference = clean_text(reference_no)
    while not reference:
        reference = clean_text(
            input_func(
                f"{_display_value(draft.company_name.value)} - Reference No.: "
            )
        )
        if not reference:
            output("A non-blank Reference No. is required.")
    return "ready", reference
