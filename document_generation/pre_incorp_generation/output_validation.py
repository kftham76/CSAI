from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from lxml import etree

from .models import DirectorContext, PreIncorpContext, ValidationIssue
from .renderer import (
    format_date,
    format_identification,
)


LEGACY_TEMPLATE_VALUES = (
    "2024B068109",
    "{ company name }",
    "HOSAY 3 BAKERY SDN. BHD.",
    "TAN HUI KEE",
    "930412-02-5193",
    "8 December 2024",
    "12 APRIL 1993",
    "MALAYSIAN/CHINESE",
    "51 Lorong Berlian Indah 3",
    "51 LORONG BERLIAN INDAH 3",
    "11 Jalan Seruling",
    "11 JALAN SERULING",
    "ahqiitan1204@gmail.com",
    "017-5962284",
    "(director)",
    "(director ic)",
)


def _signature(path: Path) -> tuple:
    document = Document(str(path))
    sections = tuple(
        (
            section.page_width,
            section.page_height,
            section.orientation,
            section.left_margin,
            section.right_margin,
            section.top_margin,
            section.bottom_margin,
            section.start_type,
        )
        for section in document.sections
    )
    tables = tuple((len(table.rows), len(table.columns)) for table in document.tables)
    with ZipFile(path) as package:
        parts = tuple(sorted(package.namelist()))
    return sections, tables, parts


def _preserve_only_parts_match(output_path: Path, template_path: Path) -> bool:
    with ZipFile(output_path) as output, ZipFile(template_path) as template:
        names = set(template.namelist())
        if names != set(output.namelist()):
            return False
        return all(
            output.read(name) == template.read(name)
            for name in names
            if name != "word/document.xml"
        )


def _all_text(path: Path) -> str:
    with ZipFile(path) as package:
        root = etree.fromstring(package.read("word/document.xml"))
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.xpath(".//w:p", namespaces=namespace):
        paragraphs.append("".join(paragraph.xpath(".//w:t/text()", namespaces=namespace)))
    return "\n".join(paragraphs)


def validate_pre_incorp_docx(
    path: Path,
    template_path: Path,
    kind: str,
    context: PreIncorpContext,
    director: DirectorContext,
    reference_no: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not path.is_file() or path.stat().st_size == 0:
        return [ValidationIssue("missing_output", f"Generated DOCX was not created: {path}", "output")]
    try:
        text = _all_text(path)
        if _signature(path) != _signature(template_path):
            issues.append(
                ValidationIssue(
                    "template_structure_changed",
                    "Generated DOCX sections, tables, or package parts differ from its retained template.",
                    "output",
                )
            )
        if not _preserve_only_parts_match(path, template_path):
            issues.append(
                ValidationIssue(
                    "preserve_only_part_changed",
                    "A package part outside word/document.xml changed from the retained template.",
                    "output",
                )
            )
    except (BadZipFile, KeyError, ValueError) as error:
        return [ValidationIssue("invalid_docx", f"Generated DOCX is invalid: {error}", "output")]

    required = [context.company_name, director.name, director.id_number]
    forbidden = list(LEGACY_TEMPLATE_VALUES)
    if kind == "s201":
        required.extend([reference_no, format_date(context.declaration_date), "Section 201"])
        if "NOTICE UNDER SECTIONS 57, 219 AND 221" in text:
            issues.append(ValidationIssue("template_interchanged", "Director's Notice content appeared in the S201 output.", "output"))
    elif kind == "notice":
        required.extend(
            [
                format_date(director.date_of_birth, uppercase=True),
                format_identification(director.id_number, director.id_type),
                "57, 219 AND 221",
            ]
        )
        if format_date(context.declaration_date) in text:
            issues.append(ValidationIssue("notice_date_filled", "The Notice signature date must remain blank.", "output"))
        if "Section 201" in text:
            issues.append(ValidationIssue("template_interchanged", "S201 content appeared in the Director's Notice output.", "output"))
    for value in required:
        if value and value not in text:
            issues.append(ValidationIssue("missing_generated_value", f"Generated DOCX is missing: {value}", "output"))
    for value in forbidden:
        if value and value in text and value not in required:
            issues.append(ValidationIssue("sample_value_leaked", f"Template sample value remains: {value}", "output"))
    if "{{" in text or "}}" in text:
        issues.append(
            ValidationIssue(
                "unresolved_template_marker",
                "Generated DOCX contains an unresolved {{ ... }} template marker.",
                "output",
            )
        )
    return issues
