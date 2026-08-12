from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.oxml.ns import qn

from .models import ValidationIssue
from .template_selection import TEMPLATE_SECTION_90


def _all_document_text(document: Document) -> str:
    """Return visible paragraph text from the complete document body.

    ``Document.paragraphs`` omits paragraphs inside tables and Word can split a
    visually continuous heading across multiple runs. Reading the underlying
    paragraph elements keeps validation independent of those layout details.
    """
    paragraph_texts: list[str] = []
    for paragraph in document.element.body.iter(qn("w:p")):
        parts: list[str] = []
        for child in paragraph.iter():
            if child.tag == qn("w:t"):
                parts.append(child.text or "")
            elif child.tag in {qn("w:tab"), qn("w:br"), qn("w:cr")}:
                parts.append(" ")
        paragraph_texts.append("".join(parts))
    return "\n".join(paragraph_texts)


def validate_output_docx(path: Path, template_family: str = "standard") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not path.is_file() or path.stat().st_size == 0:
        return [
            ValidationIssue(
                code="missing_output",
                message=f"Generated DOCX was not created: {path}",
                source="output",
            )
        ]
    try:
        with ZipFile(path) as package:
            xml_text = "\n".join(
                package.read(name).decode("utf-8", errors="ignore")
                for name in package.namelist()
                if name.endswith(".xml")
            )
    except BadZipFile:
        return [
            ValidationIssue(
                code="invalid_docx",
                message="Generated file is not a valid DOCX package.",
                source="output",
            )
        ]
    if "{{" in xml_text or "}}" in xml_text:
        issues.append(
            ValidationIssue(
                code="unresolved_template_marker",
                message="Generated DOCX contains an unresolved template marker.",
                source="output",
            )
        )
    try:
        document = Document(str(path))
    except Exception as error:  # pragma: no cover - defensive library boundary
        issues.append(
            ValidationIssue(
                code="docx_open_failed",
                message=f"python-docx could not open the generated file: {error}",
                source="output",
            )
        )
        return issues
    full_text = _all_document_text(document)
    normalized_text = " ".join(full_text.split())
    authority_resolution_headings = (
        "AUTHORITY TO FILE AUDITED FINANCIAL STATEMENTS",
        "AUTHORITY TO LODGE AUDITED FINANCIAL STATEMENTS",
    )
    if template_family != TEMPLATE_SECTION_90 and not any(
        heading in normalized_text
        for heading in authority_resolution_headings
    ):
        issues.append(
            ValidationIssue(
                code="missing_authority_resolution",
                message="The DWR Authority to File/Lodge resolution is required.",
                source="output",
            )
        )
    if "Client master" in full_text or "Constitution file" in full_text:
        issues.append(
            ValidationIssue(
                code="source_annotation_leaked",
                message="A source annotation remains in the generated document.",
                source="output",
            )
        )
    return issues
