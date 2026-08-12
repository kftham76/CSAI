from __future__ import annotations

import re
import unicodedata
from pathlib import Path


TEMPLATE_STANDARD = "standard"
TEMPLATE_PARAGRAPH_15 = "paragraph_15"
# Backwards-compatible semantic alias: this family now represents every DWR
# authority that may select either the standard or first-AGM template.
TEMPLATE_STANDARD_OR_FIRST_AGM = TEMPLATE_PARAGRAPH_15
TEMPLATE_FIRST_AGM = "first_agm"
TEMPLATE_SECTION_90 = "section_90"


_STANDARD_OR_FIRST_AGM_ARTICLES = ("23 B", "34", "36", "37")
_SECTION_90_ARTICLES = ("3 D", "5", "9", "72", "77", "95")


def normalize_dwr_for_matching(value: str) -> str:
    """Return a punctuation- and encoding-tolerant DWR matching string."""
    text = unicodedata.normalize("NFKD", str(value or "")).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _has_numbered_authority(normalized: str, authority: str, reference: str) -> bool:
    """Match one complete authority reference without prefix collisions."""
    pattern = rf"\b{re.escape(authority)}\s+{re.escape(reference)}\b"
    return re.search(pattern, normalized) is not None


def classify_dwr(value: str) -> str:
    normalized = normalize_dwr_for_matching(value)

    is_articles_of_association = "ARTICLES OF ASSOCIATION" in normalized
    if (
        _has_numbered_authority(normalized, "REGULATION", "90")
        and "TABLE A" in normalized
        and is_articles_of_association
    ):
        return TEMPLATE_SECTION_90
    if (
        is_articles_of_association
        and any(
            _has_numbered_authority(normalized, "ARTICLE", reference)
            for reference in _SECTION_90_ARTICLES
        )
    ):
        return TEMPLATE_SECTION_90
    if (
        _has_numbered_authority(normalized, "CLAUSE", "53")
        and "CONSTITUTION" in normalized
    ):
        return TEMPLATE_SECTION_90

    if (
        _has_numbered_authority(normalized, "PARAGRAPH", "15")
        and "THIRD SCHEDULE" in normalized
    ):
        return TEMPLATE_STANDARD_OR_FIRST_AGM
    if (
        "CONSTITUTION" in normalized
        and not is_articles_of_association
        and any(
            _has_numbered_authority(normalized, "ARTICLE", reference)
            for reference in _STANDARD_OR_FIRST_AGM_ARTICLES
        )
    ):
        return TEMPLATE_STANDARD_OR_FIRST_AGM
    if (
        _has_numbered_authority(normalized, "REGULATION", "34")
        and "CONSTITUTION" in normalized
        and not is_articles_of_association
    ):
        return TEMPLATE_STANDARD_OR_FIRST_AGM
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
