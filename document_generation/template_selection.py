from __future__ import annotations

import re
import unicodedata
from pathlib import Path


TEMPLATE_STANDARD = "standard"
TEMPLATE_PARAGRAPH_15 = "paragraph_15"
TEMPLATE_FIRST_AGM = "first_agm"
TEMPLATE_SECTION_90 = "section_90"


def normalize_dwr_for_matching(value: str) -> str:
    """Return a punctuation- and encoding-tolerant DWR matching string."""
    text = unicodedata.normalize("NFKD", str(value or "")).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_dwr(value: str) -> str:
    normalized = normalize_dwr_for_matching(value)
    if all(
        token in normalized
        for token in ("REGULATION 90", "TABLE A", "ARTICLES OF ASSOCIATION")
    ):
        return TEMPLATE_SECTION_90
    if all(token in normalized for token in ("PARAGRAPH 15", "THIRD SCHEDULE")):
        return TEMPLATE_PARAGRAPH_15
    return TEMPLATE_STANDARD


def infer_override_family(path: Path, automatic_family: str) -> str:
    name = path.name.lower().replace(" ", "_")
    if "section_90" in name or "section90" in name:
        return TEMPLATE_SECTION_90
    if "first_agm" in name:
        return TEMPLATE_FIRST_AGM
    if path.name.lower() == "agm_approve_accounts_template.docx":
        return TEMPLATE_STANDARD
    return automatic_family
