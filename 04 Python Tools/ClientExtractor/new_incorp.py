"""Build the vertical New Incorporation workbook for every master client.

The client master remains the authority for the current company, director, and
member state.  The newest valid Section 14 and EBOS documents enrich that
state and are also retained verbatim in filing-specific workbook sections.

Workbook authoring is delegated to ``new_incorp_workbook.mjs`` so the final
XLSX is produced by the bundled @oai/artifact-tool runtime.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable
import warnings

import pandas as pd
from pypdf import PdfReader


CLIENT_ROOT = Path(r"D:\CSAI_CLIENTS")
MASTER_FILE = Path(r"D:\CSAI_DATA\Database\clients_master.xlsx")
OUTPUT_FILE = Path(r"D:\CSAI_DATA\Database\New Incorp 123456.xlsx")
WRITER_FILE = Path(__file__).with_name("new_incorp_workbook.mjs")

MAX_DIRECTORS = 5
MAX_MEMBERS = 6
MAX_S14_DIRECTORS = 5
MAX_S14_MEMBERS = 6
MAX_BUSINESS_ACTIVITIES = 5
MAX_BENEFICIAL_OWNERS = 4

SECTION14_RE = re.compile(r"super\s*form|section[\s_-]*14|\bs14\b", re.I)
EBOS_RE = re.compile(r"e[\s_-]*bos|ebos", re.I)
DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

DIRECTOR_FIELDS = (
    "Name", "IC", "ID Type", "DOB", "Passport Expiry", "Nationality",
    "Citizenship", "Race", "Gender", "Designation",
    "Business Occupation", "Residential Address", "Service Address",
    "Email", "Contact No", "Appointment Date",
)
MEMBER_FIELDS = (
    "Type", "Name", "ID Type", "ID No", "Nationality", "Race", "Gender",
    "DOB", "Address", "Shares", "Share Type", "Analysis", "Email",
    "Contact No", "Price per Share",
)
S14_DIRECTOR_FIELDS = (
    "Name", "ID Type", "Identification No", "Nationality", "Address",
    "DOB", "Race", "Email",
)
S14_MEMBER_FIELDS = (
    "Name", "ID Type", "Identification No", "Nationality", "Address",
    "Race", "Email", "Price per Share", "Class of Share", "Number of Shares",
)
BO_FIELDS = (
    "Application Type", "Status", "Date of Becoming BO", "Date of Cessation",
    "Reason", "Date of Data Recorded", "Type", "Category", "Name",
    "Identification No", "DOB", "Gender", "Race", "Nationality",
    "Citizenship", "Designation", "Residential Address", "Business Address",
    "Email", "Contact No", "Type of BO", "Criteria A - Direct Ownership %",
    "Criteria B - Voting Shares %", "Criteria C",
)

MASTER_REQUIRED_COLUMNS = (
    "Folder", "Company Name", "Reg No", "Director1 Name", "Member1 Name",
    "UpdatedAt",
)

warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")


def clean(value: Any) -> str:
    """Return stable, single-spaced text without turning blanks into 'nan'."""
    if value is None or pd.isna(value):
        return ""
    text = (
        str(value)
        .replace("\xa0", " ")
        .replace("\ufffd", " ")
        .replace("\xad", "-")
    )
    return re.sub(r"\s+", " ", text).strip()


def clean_multiline(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\ufffd", " ").replace("\xad", "-")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_identity(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean(value).upper())


def normalize_name(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", clean(value).upper()).strip()


def registration_tokens(value: Any) -> set[str]:
    text = clean(value).upper()
    tokens = set(re.findall(r"(?<!\d)\d{12}(?!\d)", text))
    tokens.update(re.findall(r"(?<![A-Z0-9])\d{6,7}-?[A-Z](?![A-Z0-9])", text))
    return {re.sub(r"[^A-Z0-9]", "", token) for token in tokens}


def parse_date(value: Any) -> datetime | None:
    text = clean(value)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def parse_received_datetime(text: str) -> datetime | None:
    match = re.search(
        r"Date\s*&\s*Time\s*Received\s+(\d{2}/\d{2}/\d{4})\s+"
        r"(\d{1,2}:\d{2}\s*(?:AM|PM))",
        text,
        re.I,
    )
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)} {match.group(2).upper()}", "%d/%m/%Y %I:%M %p")
    except ValueError:
        return None


def date_from_filename(path: Path) -> datetime | None:
    values: list[datetime] = []
    stem = path.stem
    for year, month, day in re.findall(r"(?<!\d)(20\d{2})[-_. ]?([01]\d)[-_. ]?([0-3]\d)(?!\d)", stem):
        try:
            values.append(datetime(int(year), int(month), int(day)))
        except ValueError:
            pass
    for day, month, year in re.findall(r"(?<!\d)([0-3]\d)[-_. ]([01]\d)[-_. ](20\d{2})(?!\d)", stem):
        try:
            values.append(datetime(int(year), int(month), int(day)))
        except ValueError:
            pass
    return max(values) if values else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pdf_text(path: Path) -> str:
    try:
        reader = PdfReader(path)
        return clean_multiline("\n".join(page.extract_text() or "" for page in reader.pages))
    except Exception:
        return ""


def try_ocr_pdf(path: Path) -> str:
    """Best-effort OCR for a likely source whose text layer is empty."""
    try:
        import numpy as np
        import pypdfium2
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
        document = pypdfium2.PdfDocument(str(path))
        lines: list[str] = []
        try:
            for page in document:
                image = page.render(scale=2.3).to_pil()
                result, _ = engine(np.asarray(image))
                if result:
                    lines.extend(item[1] for item in result if len(item) > 1)
        finally:
            document.close()
        return clean_multiline("\n".join(lines))
    except Exception:
        return ""


def is_section14_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).upper()
    return "APPLICATIONFORREGISTRATIONOFACOMPANY" in compact and "PARTICULARSOFCOMPANY" in compact


def is_ebos_text(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).upper()
    return (
        "NOTIFICATION OF BENEFICIAL OWNERSHIP INFORMATION" in compact
        and "DIVISION 8A" in compact
        and "COMPANIES ACT 2016" in compact
    )


def extract_document_registration(text: str) -> str:
    patterns = (
        r"Registration\s+No\.?\s*:?[ \t]*([^\n]+)",
        r"COMPANY\s+NO\s*:?[ \t]*([^\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean(match.group(1))
    return ""


def registration_state(document_value: str, master_value: str) -> int:
    document = registration_tokens(document_value)
    master = registration_tokens(master_value)
    if not document:
        return 1
    return 2 if document & master else 0


def revision_number(path: Path) -> int:
    matches = re.findall(r"(?:\(|\b)R\s*(\d+)(?:\)|\b)", path.stem, re.I)
    return max((int(value) for value in matches), default=0)


def preferred_folder_score(path: Path, family: str) -> int:
    parts = [re.sub(r"[^A-Z0-9]", "", part.upper()) for part in path.parts]
    if family == "S14":
        return 2 if "FORM" in parts else 1 if "STATUTORYAUDIT" in parts else 0
    return 2 if "EBOS" in parts else 1 if "BO" in parts else 0


@dataclass
class Candidate:
    family: str
    path: Path
    relative_path: str
    text: str
    sha256: str
    registration_no: str
    registration_match: int
    document_datetime: datetime | None
    filename_datetime: datetime | None
    mtime_ns: int
    revision: int = 0
    submission_number: str = ""
    parsed: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def selected_datetime(self) -> datetime:
        return self.document_datetime or self.filename_datetime or datetime.fromtimestamp(self.mtime_ns / 1_000_000_000)


def _extract_s14_datetime(text: str) -> datetime | None:
    values = []
    for label in ("Date of Application", "Incorporation Date"):
        match = re.search(rf"{label}\s*:?[ \t]*(\d{{2}}/\d{{2}}/\d{{4}})", text, re.I)
        if match and parse_date(match.group(1)):
            values.append(parse_date(match.group(1)))
    return max((value for value in values if value), default=None)


def _submission_number(text: str) -> str:
    match = re.search(r"Submission\s+Number\s+([^\s]+)", text, re.I)
    return clean(match.group(1)) if match else ""


def _submission_rank(value: str) -> int:
    match = re.search(r"(\d+)$", value)
    return int(match.group(1)) if match else 0


def candidate_rank(candidate: Candidate) -> tuple[Any, ...]:
    if candidate.family == "S14":
        return (
            candidate.selected_datetime,
            candidate.registration_match,
            candidate.revision,
            preferred_folder_score(candidate.path, "S14"),
            candidate.mtime_ns,
            candidate.relative_path.lower(),
        )
    return (
        candidate.selected_datetime,
        candidate.registration_match,
        _submission_rank(candidate.submission_number),
        preferred_folder_score(candidate.path, "EBOS"),
        candidate.mtime_ns,
        candidate.relative_path.lower(),
    )


def deduplicate_candidates(candidates: Iterable[Candidate]) -> list[Candidate]:
    selected: dict[str, Candidate] = {}
    for candidate in candidates:
        existing = selected.get(candidate.sha256)
        if existing is None or candidate_rank(candidate) > candidate_rank(existing):
            selected[candidate.sha256] = candidate
    return list(selected.values())


def discover_candidates(
    folder: Path,
    master_registration: str,
    family: str,
    allow_ocr: bool = True,
) -> list[Candidate]:
    name_pattern = SECTION14_RE if family == "S14" else EBOS_RE
    validator = is_section14_text if family == "S14" else is_ebos_text
    candidates: list[Candidate] = []
    for path in sorted(folder.rglob("*.pdf"), key=lambda item: str(item).lower()):
        if not name_pattern.search(path.name):
            continue
        text = read_pdf_text(path)
        used_ocr = False
        if not validator(text) and allow_ocr and len(clean(text)) < 120:
            ocr_text = try_ocr_pdf(path)
            if validator(ocr_text):
                text = ocr_text
                used_ocr = True
        if not validator(text):
            continue
        document_registration = extract_document_registration(text)
        match_state = registration_state(document_registration, master_registration)
        if match_state == 0:
            continue
        stat = path.stat()
        parsed = parse_section14(text) if family == "S14" else parse_ebos(text)
        candidate = Candidate(
            family=family,
            path=path,
            relative_path=str(path.relative_to(folder)),
            text=text,
            sha256=sha256_file(path),
            registration_no=document_registration,
            registration_match=match_state,
            document_datetime=(
                _extract_s14_datetime(text)
                if family == "S14"
                else parse_received_datetime(text)
            ),
            filename_datetime=date_from_filename(path),
            mtime_ns=stat.st_mtime_ns,
            revision=revision_number(path),
            submission_number=_submission_number(text),
            parsed=parsed,
        )
        if used_ocr:
            candidate.warnings.append("OCR used because the PDF text layer was insufficient")
        if match_state == 1:
            candidate.warnings.append("Document registration number was not available for cross-checking")
        candidates.append(candidate)
    return deduplicate_candidates(candidates)


def select_latest_candidate(candidates: Iterable[Candidate]) -> Candidate | None:
    return max(candidates, key=candidate_rank, default=None)


def _value_after_label(text: str, label: str, stops: Iterable[str]) -> str:
    stop_pattern = "|".join(re.escape(stop) for stop in stops)
    match = re.search(
        rf"(?:^|\n){label}\s*:?[ \t]*(.*?)(?=\n(?:{stop_pattern})\s*:?[ \t]*|\Z)",
        text,
        re.I | re.S,
    )
    return clean(match.group(1)) if match else ""


def _simple_line(text: str, label: str) -> str:
    match = re.search(rf"(?:^|\n){label}\s*:?[ \t]*([^\n]*)", text, re.I)
    return clean(match.group(1)) if match else ""


def _extract_section(text: str, start: str, ends: Iterable[str]) -> str:
    end_pattern = "|".join(re.escape(value) for value in ends)
    match = re.search(rf"{re.escape(start)}\s+(.*?)(?=(?:{end_pattern})|\Z)", text, re.I | re.S)
    return match.group(1) if match else ""


def parse_section14(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "company": {}, "activities": [], "directors": [], "members": [],
        "declaration": {}, "lodger": {},
    }
    company = result["company"]
    company["Proposed Name"] = _simple_line(text, "Proposed name")
    company["Lodging Reference No"] = _simple_line(text, "Lodging Reference No")
    company["Purpose"] = _simple_line(text, "Purpose")
    company["Company Type"] = _simple_line(text, "Company Type")
    company["Sub Type"] = _simple_line(text, "Sub Type")
    company["Incorporation Date"] = _simple_line(text, "Incorporation Date")
    company["Registration No"] = _simple_line(text, r"Registration No\.")

    activity_match = re.search(
        r"General\s+nature\s+of\s+business\s+MSIC\s+Code\s+(.*?)\nBusiness\s+Description",
        text,
        re.I | re.S,
    )
    if activity_match:
        block = activity_match.group(1)
        starts = list(re.finditer(r"(?:^|\n)\s*(\d+)\s+", block))
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(block)
            value = clean(block[start.end():end])
            code_match = re.search(r"\b(\d{5})\s*$", value)
            if code_match:
                result["activities"].append({
                    "Description": clean(value[:code_match.start()]),
                    "MSIC Code": code_match.group(1),
                })

    company["Business Description"] = _value_after_label(
        text, "Business Description", ("Registered Address",)
    )
    company["Registered Address"] = _value_after_label(
        text, "Registered Address", ("Email", "Office No", "Fax number", "Business Address")
    )
    registered_tail = text
    registered_pos = re.search(r"(?:^|\n)Registered Address", text, re.I)
    business_pos = re.search(r"(?:^|\n)Business Address", text, re.I)
    if registered_pos:
        registered_tail = text[registered_pos.start():(business_pos.start() if business_pos else len(text))]
    company["Company Email"] = _simple_line(registered_tail, "Email")
    company["Company Office No"] = _simple_line(registered_tail, "Office No")
    company["Company Fax"] = _simple_line(registered_tail, "Fax number")

    business_tail = text[business_pos.start():] if business_pos else ""
    company["Business Address"] = _value_after_label(
        business_tail, "Business Address", ("Office No", "Fax number", "PARTICULARS OF DIRECTOR")
    )
    company["Business Office No"] = _simple_line(business_tail, "Office No")
    company["Business Fax"] = _simple_line(business_tail, "Fax number")

    director_block = _extract_section(text, "PARTICULARS OF DIRECTOR", ("PARTICULARS OF MEMBER", "Declaration"))
    for entry in re.split(r"(?:^|\n)Director\s+Name\s*:?[ \t]*", director_block, flags=re.I)[1:]:
        director = {
            "Name": clean(entry.splitlines()[0] if entry.splitlines() else ""),
            "ID Type": _simple_line(entry, "ID Type"),
            "Identification No": _simple_line(entry, r"Identification No\.?"),
            "Nationality": _simple_line(entry, "Nationality"),
            "Address": _value_after_label(entry, "Address", ("Date of birth", "Race", "Email")),
            "DOB": _simple_line(entry, "Date of birth"),
            "Race": _simple_line(entry, "Race"),
            "Email": _simple_line(entry, "Email"),
        }
        if director["Name"]:
            result["directors"].append(director)

    member_block = _extract_section(text, "PARTICULARS OF MEMBER", ("Declaration",))
    for entry in re.split(r"(?:^|\n)Member\s+Name\s*:?[ \t]*", member_block, flags=re.I)[1:]:
        member = {
            "Name": clean(entry.splitlines()[0] if entry.splitlines() else ""),
            "ID Type": _simple_line(entry, "ID Type"),
            "Identification No": _simple_line(entry, r"Identification No\.?"),
            "Nationality": _simple_line(entry, "Nationality"),
            "Address": _value_after_label(entry, "Address", ("Race", "Email", "Price per share", "Class of share", "Number of share")),
            "Race": _simple_line(entry, "Race"),
            "Email": _simple_line(entry, "Email"),
            "Price per Share": _simple_line(entry, "Price per share"),
            "Class of Share": _simple_line(entry, "Class of share"),
            "Number of Shares": _simple_line(entry, "Number of share"),
        }
        if member["Name"]:
            result["members"].append(member)

    declaration = _extract_section(text, "Declaration", ("ATTENTION", "Lodger Information"))
    result["declaration"] = {
        "Name": _simple_line(declaration, r"Name\s*"),
        "Date of Application": _simple_line(declaration, "Date of Application"),
    }
    lodger = _extract_section(text, "Lodger Information", ("SURUHANJAYA",))
    result["lodger"] = {
        "Name": _simple_line(lodger, "Name"),
        "Identification No": _simple_line(lodger, "NRIC") or _simple_line(lodger, r"Identification No\."),
        "Prescribed Body": _simple_line(lodger, "Prescribed body"),
        "Licence / Membership No": _simple_line(lodger, r"License No/Membership No"),
        "Address": _value_after_label(lodger, "Address", ("Phone No.", "Email", "Prescribed body", "License No/Membership No")),
        "Phone No": _simple_line(lodger, r"Phone No\."),
        "Email": _simple_line(lodger, "Email"),
    }
    return result


def _bo_value(block: str, label: str, stops: Iterable[str] = ()) -> str:
    if stops:
        return _value_after_label(block, label, stops)
    return _simple_line(block, label)


def _inline_value(block: str, label: str, stops: Iterable[str]) -> str:
    """Extract a value when the next EBOS label may share the same line."""
    stop_pattern = "|".join(stops)
    match = re.search(
        rf"{label}\s+(.+?)(?=\s+(?:{stop_pattern})\b|\n|\Z)",
        block,
        re.I | re.S,
    )
    return clean(match.group(1)) if match else ""


def parse_ebos(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "header": {}, "company": {}, "beneficial_owners": [],
        "declaration": {}, "lodger": {},
    }
    received = parse_received_datetime(text)
    result["header"] = {
        "Submission Number": _submission_number(text),
        "Date Received": received.strftime("%d/%m/%Y") if received else "",
        "Time Received": received.strftime("%I:%M %p") if received else "",
        "Received DateTime": received.isoformat(sep=" ") if received else "",
    }
    result["company"] = {
        "Company Name": _simple_line(text, "COMPANY NAME"),
        "Company No": _simple_line(text, "COMPANY NO"),
        "Company Status": _simple_line(text, "STATUS"),
    }

    parts = re.split(r"PARTICULARS\s+OF\s+BENEFICIAL\s+OWNERSHIP", text, flags=re.I)[1:]
    for part in parts:
        block = re.split(r"\nDECLARATION\b|\nLODGER\s+INFORMATION\b", part, maxsplit=1, flags=re.I)[0]
        name = _simple_line(block, "NAME")
        identification = _simple_line(block, r"IDENTIFICATION NO\.")
        if identification:
            identification = clean(re.split(r"DATE OF BIRTH", identification, flags=re.I)[0])
        type_match = re.search(r"(?:^|\n)TYPE\s+(?!OF\b)([^\n]+)", block, re.I)
        type_of_bo_values = re.findall(r"(?:^|\n)TYPE\s+OF\s+BO\s+(?!APPLICATION\b)([^\n]+)", block, re.I)
        owner = {
            "Application Type": _simple_line(block, "TYPE OF BO APPLICATION"),
            "Status": _simple_line(block, "STATUS"),
            "Date of Becoming BO": _simple_line(block, "DATE OF BECOMING BO"),
            "Date of Cessation": _simple_line(block, "DATE OF CESSATION"),
            "Reason": _value_after_label(block, "REASON", ("TYPE", "CATEGORY", "NAME")),
            "Date of Data Recorded": _simple_line(block, "DATE OF DATA RECORDED"),
            "Type": clean(type_match.group(1)) if type_match else "",
            "Category": _simple_line(block, "CATEGORY"),
            "Name": name,
            "Identification No": identification,
            "DOB": _inline_value(block, "DATE OF BIRTH", ("GENDER", "RACE", "NATIONALITY", "CITIZENSHIP")),
            "Gender": _inline_value(block, "GENDER", ("RACE", "NATIONALITY", "CITIZENSHIP")),
            "Race": _inline_value(block, "RACE", ("NATIONALITY", "CITIZENSHIP", "DESIGNATION/POSITION")),
            "Nationality": _inline_value(block, "NATIONALITY", ("CITIZENSHIP", "DESIGNATION/POSITION")),
            "Citizenship": _inline_value(block, "CITIZENSHIP", ("DESIGNATION/POSITION", "RESIDENTIAL ADDRESS")),
            "Designation": _value_after_label(block, r"DESIGNATION/POSITION IN THE\s+COMPANY", ("RESIDENTIAL ADDRESS", "BUSINESS ADDRESS")),
            "Residential Address": _value_after_label(block, "RESIDENTIAL ADDRESS", ("BUSINESS ADDRESS", "EMAIL", "CONTACT NO.")),
            "Business Address": _value_after_label(block, "BUSINESS ADDRESS", ("EMAIL", "CONTACT NO.", "TYPE OF BO")),
            "Email": _inline_value(block, "EMAIL", ("CONTACT NO\\.?", "DATE OF BECOMING BO", "TYPE OF BO")),
            "Contact No": _inline_value(block, "CONTACT NO\\.?", ("DATE OF BECOMING BO", "TYPE OF BO")),
            "Type of BO": clean(type_of_bo_values[-1]) if type_of_bo_values else "",
            "Criteria A - Direct Ownership %": "",
            "Criteria B - Voting Shares %": "",
            "Criteria C": "",
        }
        for key, pattern in (
            ("Criteria A - Direct Ownership %", r"Criteria\s+A\s*-\s*Direct\s+Ownership\s*:\s*([\d.]+)"),
            ("Criteria B - Voting Shares %", r"Criteria\s+B\s*-\s*Voting\s+Shares\s*:\s*([\d.]+)"),
            ("Criteria C", r"Criteria\s+C\s*-\s*([^\n]+)"),
        ):
            matches = re.findall(pattern, block, re.I)
            if matches:
                owner[key] = clean(matches[-1])
        if owner["Name"] or owner["Identification No"]:
            result["beneficial_owners"].append(owner)

    declaration = _extract_section(text, "DECLARATION", ("ATTENTION", "LODGER INFORMATION"))
    result["declaration"] = {
        "Name": _simple_line(declaration, "NAME"),
        "Date of Application": _simple_line(declaration, "DATE OF APPLICATION"),
    }
    lodger = _extract_section(text, "LODGER INFORMATION", ("SURUHANJAYA",))
    result["lodger"] = {
        "Name": _simple_line(lodger, "NAME"),
        "Identification No": _simple_line(lodger, r"IDENTIFICATION NO\."),
        "Address": _value_after_label(lodger, "ADDRESS", ("EMAIL ADDRESS", "PHONE NO.", "PRACTISING CERTIFICATE NO.", "PROFESSIONAL BODY TYPE", "LICENSE NO. /MEMBERSHIP NO.")),
        "Email": _simple_line(lodger, "EMAIL ADDRESS"),
        "Phone No": _simple_line(lodger, r"PHONE NO\."),
        "Practising Certificate No": _simple_line(lodger, r"PRACTISING CERTIFICATE NO\."),
        "Professional Body Type": _simple_line(lodger, "PROFESSIONAL BODY TYPE"),
        "Licence / Membership No": _simple_line(lodger, r"LICENSE NO\. /MEMBERSHIP NO\."),
    }
    return result


def person_match(current_id: str, current_name: str, person: dict[str, Any]) -> bool:
    person_id = person.get("Identification No") or person.get("IC") or person.get("ID No")
    if normalize_identity(current_id) and normalize_identity(person_id):
        return normalize_identity(current_id) == normalize_identity(person_id)
    return bool(normalize_name(current_name) and normalize_name(current_name) == normalize_name(person.get("Name")))


def first_matching(current_id: str, current_name: str, people: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return next((person for person in people if person_match(current_id, current_name, person)), {})


def fill_if_blank(row: dict[str, str], key: str, *values: Any) -> None:
    if clean(row.get(key)):
        return
    for value in values:
        if clean(value):
            row[key] = clean(value)
            return


def enrich_current_people(
    master_row: dict[str, str],
    s14: dict[str, Any],
    ebos: dict[str, Any],
) -> dict[str, str]:
    row = {key: clean(value) for key, value in master_row.items()}
    s14_directors = s14.get("directors", [])
    s14_members = s14.get("members", [])
    owners = ebos.get("beneficial_owners", [])

    for index in range(1, MAX_DIRECTORS + 1):
        name = row.get(f"Director{index} Name", "")
        identifier = row.get(f"Director{index} IC", "")
        if not name and not identifier:
            continue
        owner = first_matching(identifier, name, owners)
        original = first_matching(identifier, name, s14_directors)
        mappings = {
            "ID Type": (original.get("ID Type"),),
            "DOB": (owner.get("DOB"), original.get("DOB")),
            "Nationality": (owner.get("Nationality"), original.get("Nationality")),
            "Citizenship": (owner.get("Citizenship"),),
            "Race": (owner.get("Race"), original.get("Race")),
            "Gender": (owner.get("Gender"),),
            "Designation": (owner.get("Designation"),),
            "Residential Address": (owner.get("Residential Address"), original.get("Address")),
            "Email": (owner.get("Email"), original.get("Email")),
            "Contact No": (owner.get("Contact No"),),
        }
        for field_name, values in mappings.items():
            fill_if_blank(row, f"Director{index} {field_name}", *values)

    for index in range(1, MAX_MEMBERS + 1):
        name = row.get(f"Member{index} Name", "")
        identifier = row.get(f"Member{index} ID No", "")
        owner = first_matching(identifier, name, owners)
        original = first_matching(identifier, name, s14_members)
        mappings = {
            "ID Type": (original.get("ID Type"),),
            "Nationality": (owner.get("Nationality"), original.get("Nationality")),
            "Race": (owner.get("Race"), original.get("Race")),
            "Gender": (owner.get("Gender"),),
            "DOB": (owner.get("DOB"),),
            "Address": (owner.get("Residential Address"), original.get("Address")),
            "Email": (owner.get("Email"), original.get("Email")),
            "Contact No": (owner.get("Contact No"),),
            "Price per Share": (original.get("Price per Share"),),
        }
        for field_name, values in mappings.items():
            fill_if_blank(row, f"Member{index} {field_name}", *values)
    return row


def typed_value(field_name: str, value: Any) -> tuple[Any, str]:
    text = clean(value)
    if not text:
        return "", "text"
    if field_name == "UpdatedAt":
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=False)
        if not pd.isna(parsed):
            return parsed.to_pydatetime().isoformat(), "datetime"
    if "Received DateTime" in field_name:
        parsed = pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=True)
        if not pd.isna(parsed):
            return parsed.to_pydatetime().isoformat(), "datetime"
    if field_name.endswith(" Date") or field_name.endswith(" DOB") or field_name in {
        "Annual Return Date", "Date of Lodgement (AR)", "Section 51 Date",
        "Section 58 Date", "Section 78 Date", "Incorporate Date",
    }:
        parsed = pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=True)
        if not pd.isna(parsed):
            return parsed.date().isoformat(), "date"
    return text, "text"


def make_row(field_name: str, value: Any = "", auxiliary: Any = "") -> dict[str, Any]:
    typed, value_type = typed_value(field_name, value)
    return {
        "field": field_name,
        "value": typed,
        "auxiliary": clean(auxiliary),
        "valueType": value_type,
    }


def make_company_sections(
    current: dict[str, str],
    s14: dict[str, Any],
    ebos: dict[str, Any],
    s14_candidate: Candidate | None,
    ebos_candidate: Candidate | None,
    folder_status: str,
    updated_at: str,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    base_fields = (
        "Folder", "Company Name", "Reg No", "Annual Return Date",
        "Date of Lodgement (AR)", "Section 51 Date", "Section 58 Date",
        "Section 78 Date", "Incorporate Date", "Total Issued Shares",
        "Business Address", "Financial Record Address",
    )
    sections.append({
        "title": "Current Company Profile",
        "rows": [make_row(field_name, current.get(field_name, "")) for field_name in base_fields],
    })

    company = s14.get("company", {})
    s14_rows = [
        make_row("S14 Proposed Name", company.get("Proposed Name")),
        make_row("S14 Registration No", company.get("Registration No")),
        make_row("S14 Lodging Reference No", company.get("Lodging Reference No")),
        make_row("S14 Purpose", company.get("Purpose")),
        make_row("S14 Company Type", company.get("Company Type")),
        make_row("S14 Sub Type", company.get("Sub Type")),
        make_row("S14 Incorporation Date", company.get("Incorporation Date")),
    ]
    activities = s14.get("activities", [])
    for index in range(MAX_BUSINESS_ACTIVITIES):
        activity = activities[index] if index < len(activities) else {}
        s14_rows.append(make_row(f"S14 Business Activity{index + 1} Description", activity.get("Description")))
        s14_rows.append(make_row(f"S14 Business Activity{index + 1} MSIC Code", activity.get("MSIC Code")))
    s14_rows.extend([
        make_row("S14 Business Description", company.get("Business Description")),
        make_row("S14 Registered Address", company.get("Registered Address")),
        make_row("S14 Company Email", company.get("Company Email")),
        make_row("S14 Company Office No", company.get("Company Office No")),
        make_row("S14 Company Fax", company.get("Company Fax")),
        make_row("S14 Business Address", company.get("Business Address")),
        make_row("S14 Business Office No", company.get("Business Office No")),
        make_row("S14 Business Fax", company.get("Business Fax")),
    ])
    sections.append({"title": "Section 14 - Company", "rows": s14_rows})

    director_rows = []
    for index in range(1, MAX_DIRECTORS + 1):
        director_rows.extend(make_row(f"Director{index} {field_name}", current.get(f"Director{index} {field_name}")) for field_name in DIRECTOR_FIELDS)
    sections.append({"title": "Current Directors", "rows": director_rows})

    member_rows = []
    for index in range(1, MAX_MEMBERS + 1):
        member_rows.extend(make_row(f"Member{index} {field_name}", current.get(f"Member{index} {field_name}")) for field_name in MEMBER_FIELDS)
    sections.append({"title": "Current Members", "rows": member_rows})

    s14_director_rows = []
    s14_directors = s14.get("directors", [])
    for index in range(MAX_S14_DIRECTORS):
        person = s14_directors[index] if index < len(s14_directors) else {}
        s14_director_rows.extend(make_row(f"S14 Director{index + 1} {field_name}", person.get(field_name)) for field_name in S14_DIRECTOR_FIELDS)
    sections.append({"title": "Section 14 - Incorporation Directors", "rows": s14_director_rows})

    s14_member_rows = []
    s14_members = s14.get("members", [])
    for index in range(MAX_S14_MEMBERS):
        person = s14_members[index] if index < len(s14_members) else {}
        s14_member_rows.extend(make_row(f"S14 Member{index + 1} {field_name}", person.get(field_name)) for field_name in S14_MEMBER_FIELDS)
    sections.append({"title": "Section 14 - Incorporation Members", "rows": s14_member_rows})

    declaration = s14.get("declaration", {})
    lodger = s14.get("lodger", {})
    sections.append({
        "title": "Section 14 - Declaration and Lodger",
        "rows": [
            make_row("S14 Declaration Name", declaration.get("Name")),
            make_row("S14 Declaration Date of Application", declaration.get("Date of Application")),
            make_row("S14 Lodger Name", lodger.get("Name")),
            make_row("S14 Lodger Identification No", lodger.get("Identification No")),
            make_row("S14 Lodger Prescribed Body", lodger.get("Prescribed Body")),
            make_row("S14 Lodger Licence / Membership No", lodger.get("Licence / Membership No")),
            make_row("S14 Lodger Address", lodger.get("Address")),
            make_row("S14 Lodger Phone No", lodger.get("Phone No")),
            make_row("S14 Lodger Email", lodger.get("Email")),
        ],
    })

    header = ebos.get("header", {})
    ebos_company = ebos.get("company", {})
    sections.append({
        "title": "Latest EBOS Filing",
        "rows": [
            make_row("EBOS Submission Number", header.get("Submission Number")),
            make_row("EBOS Date Received", header.get("Date Received")),
            make_row("EBOS Time Received", header.get("Time Received")),
            make_row("EBOS Received DateTime", header.get("Received DateTime")),
            make_row("EBOS Company Name", ebos_company.get("Company Name")),
            make_row("EBOS Company No", ebos_company.get("Company No")),
            make_row("EBOS Company Status", ebos_company.get("Company Status")),
        ],
    })

    owners = ebos.get("beneficial_owners", [])
    if len(owners) > MAX_BENEFICIAL_OWNERS:
        raise ValueError(
            f"{current.get('Folder')}: latest EBOS filing contains {len(owners)} BO entries; "
            f"the workbook supports {MAX_BENEFICIAL_OWNERS}."
        )
    owner_rows = []
    for index in range(MAX_BENEFICIAL_OWNERS):
        owner = owners[index] if index < len(owners) else {}
        owner_rows.extend(make_row(f"BO{index + 1} {field_name}", owner.get(field_name)) for field_name in BO_FIELDS)
    sections.append({"title": "Latest EBOS - Beneficial Owners", "rows": owner_rows})

    declaration = ebos.get("declaration", {})
    lodger = ebos.get("lodger", {})
    sections.append({
        "title": "Latest EBOS - Declaration and Lodger",
        "rows": [
            make_row("EBOS Declaration Name", declaration.get("Name")),
            make_row("EBOS Declaration Date of Application", declaration.get("Date of Application")),
            make_row("EBOS Lodger Name", lodger.get("Name")),
            make_row("EBOS Lodger Identification No", lodger.get("Identification No")),
            make_row("EBOS Lodger Address", lodger.get("Address")),
            make_row("EBOS Lodger Email", lodger.get("Email")),
            make_row("EBOS Lodger Phone No", lodger.get("Phone No")),
            make_row("EBOS Lodger Practising Certificate No", lodger.get("Practising Certificate No")),
            make_row("EBOS Lodger Professional Body Type", lodger.get("Professional Body Type")),
            make_row("EBOS Lodger Licence / Membership No", lodger.get("Licence / Membership No")),
        ],
    })

    def audit_rows(prefix: str, candidate: Candidate | None, missing_status: str) -> list[dict[str, Any]]:
        if candidate:
            status = "OK" if not candidate.warnings else "OK_WITH_WARNINGS"
            source = candidate.relative_path
            selected_date = candidate.selected_datetime.isoformat(sep=" ")
            digest = candidate.sha256
            warning_text = "; ".join(candidate.warnings)
        else:
            status = missing_status
            source = selected_date = digest = warning_text = ""
        return [
            make_row(f"{prefix} Extraction Status", status),
            make_row(f"{prefix} Source PDF", source),
            make_row(f"{prefix} Selected DateTime", selected_date),
            make_row(f"{prefix} SHA256", digest),
            make_row(f"{prefix} Extraction Warnings", warning_text),
        ]

    s14_missing = "MISSING_CLIENT_FOLDER" if folder_status != "OK" else "NO_VALID_SECTION14"
    ebos_missing = "MISSING_CLIENT_FOLDER" if folder_status != "OK" else "NO_VALID_EBOS"
    audit = [make_row("Client Folder Status", folder_status)]
    audit.extend(audit_rows("Section 14", s14_candidate, s14_missing))
    audit.extend(audit_rows("EBOS", ebos_candidate, ebos_missing))
    audit.append(make_row("UpdatedAt", updated_at))
    sections.append({"title": "Source Audit", "rows": audit})
    return sections


def load_master(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Master workbook not found: {path}")
    frame = pd.read_excel(path, sheet_name="Sheet1", dtype=str, keep_default_na=False)
    missing = [column for column in MASTER_REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Master workbook is missing required columns: {', '.join(missing)}")
    if len(frame) != 80:
        raise ValueError(f"Expected exactly 80 master companies, found {len(frame)}")
    folders = [clean(value) for value in frame["Folder"]]
    if any(not value for value in folders) or len(set(folders)) != len(folders):
        raise ValueError("Master Folder values must be nonblank and unique")
    return [{column: clean(value) for column, value in row.items()} for row in frame.to_dict(orient="records")]


def safe_sheet_name(sequence: int, folder: str, used: set[str]) -> str:
    cleaned = re.sub(r"[\\/*?:\[\]]", " ", folder)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    base = f"{sequence:03d} {cleaned}"[:31].rstrip()
    name = base
    counter = 2
    while name.casefold() in used:
        suffix = f" {counter}"
        name = f"{base[:31 - len(suffix)].rstrip()}{suffix}"
        counter += 1
    used.add(name.casefold())
    return name


def resolve_client_directories(client_root: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    """Return exact and unambiguous normalized client-folder lookups."""
    paths = [path for path in client_root.iterdir() if path.is_dir()]
    exact = {path.name: path for path in paths}
    groups: dict[str, list[Path]] = {}
    for path in paths:
        groups.setdefault(normalize_name(path.name), []).append(path)
    normalized = {
        key: values[0]
        for key, values in groups.items()
        if key and len(values) == 1
    }
    return exact, normalized


def build_payload(
    client_root: Path = CLIENT_ROOT,
    master_file: Path = MASTER_FILE,
    allow_ocr: bool = True,
) -> dict[str, Any]:
    master_rows = load_master(master_file)
    directories, normalized_directories = resolve_client_directories(client_root)
    updated_at = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    sheets = []
    index_rows = []
    used_names: set[str] = set()

    for sequence, master_row in enumerate(master_rows, start=1):
        folder_name = master_row["Folder"]
        folder = directories.get(folder_name) or normalized_directories.get(normalize_name(folder_name))
        folder_status = "OK" if folder else "MISSING_CLIENT_FOLDER"
        s14_candidate = None
        ebos_candidate = None
        if folder:
            s14_candidate = select_latest_candidate(discover_candidates(folder, master_row["Reg No"], "S14", allow_ocr))
            ebos_candidate = select_latest_candidate(discover_candidates(folder, master_row["Reg No"], "EBOS", allow_ocr))
        s14 = s14_candidate.parsed if s14_candidate else {}
        ebos = ebos_candidate.parsed if ebos_candidate else {}
        current = enrich_current_people(master_row, s14, ebos)
        sheet_name = safe_sheet_name(sequence, folder_name, used_names)
        sections = make_company_sections(
            current, s14, ebos, s14_candidate, ebos_candidate,
            folder_status, updated_at,
        )
        sheets.append({
            "name": sheet_name,
            "title": current.get("Company Name") or folder_name,
            "sections": sections,
        })
        index_rows.append({
            "Sequence": sequence,
            "Worksheet": sheet_name,
            "Folder": folder_name,
            "Company Name": current.get("Company Name", ""),
            "Reg No": current.get("Reg No", ""),
            "Section 14 Status": "OK" if s14_candidate else ("MISSING_CLIENT_FOLDER" if not folder else "NO_VALID_SECTION14"),
            "Section 14 Source": s14_candidate.relative_path if s14_candidate else "",
            "EBOS Status": "OK" if ebos_candidate else ("MISSING_CLIENT_FOLDER" if not folder else "NO_VALID_EBOS"),
            "EBOS Source": ebos_candidate.relative_path if ebos_candidate else "",
        })
        print(
            f"[{sequence:02d}/80] {folder_name}: "
            f"S14={'yes' if s14_candidate else 'no'}, EBOS={'yes' if ebos_candidate else 'no'}",
            flush=True,
        )
    return {
        "generatedAt": updated_at,
        "index": index_rows,
        "sheets": sheets,
    }


def resolve_node_runtime() -> tuple[Path, Path]:
    node = os.environ.get("CSAI_NODE", "").strip()
    modules = os.environ.get("CSAI_NODE_MODULES", "").strip()
    runtime_root = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies"
    node_path = Path(node) if node else runtime_root / "node" / "bin" / "node.exe"
    modules_path = Path(modules) if modules else runtime_root / "node" / "node_modules"
    if not node_path.is_file():
        located = shutil.which("node")
        if located:
            node_path = Path(located)
    if not node_path.is_file():
        raise FileNotFoundError("Node.js runtime was not found; set CSAI_NODE")
    if not modules_path.is_dir():
        raise FileNotFoundError("Bundled node_modules was not found; set CSAI_NODE_MODULES")
    return node_path, modules_path


def _make_junction(link: Path, target: Path) -> None:
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise RuntimeError(f"Could not create temporary node_modules junction: {completed.stderr or completed.stdout}")
    else:
        link.symlink_to(target, target_is_directory=True)


def write_workbook(payload: dict[str, Any], output_file: Path) -> None:
    if not WRITER_FILE.is_file():
        raise FileNotFoundError(f"Workbook writer not found: {WRITER_FILE}")
    if output_file.suffix.lower() != ".xlsx":
        raise ValueError("The extractor output must use the .xlsx extension")
    node, node_modules = resolve_node_runtime()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_file.with_name(f".{output_file.stem}.{os.getpid()}.tmp.xlsx")
    inspect_sidecar = Path(f"{temp_output}.inspect.ndjson")
    if temp_output.exists():
        temp_output.unlink()
    try:
        with tempfile.TemporaryDirectory(prefix="new-incorp-") as directory:
            working = Path(directory)
            payload_file = working / "payload.json"
            writer_copy = working / "new_incorp_workbook.mjs"
            payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            shutil.copy2(WRITER_FILE, writer_copy)
            _make_junction(working / "node_modules", node_modules)
            completed = subprocess.run(
                [str(node), str(writer_copy), str(payload_file), str(temp_output)],
                cwd=working,
                text=True,
            )
            if completed.returncode:
                raise RuntimeError(f"Workbook writer exited with code {completed.returncode}")
        os.replace(temp_output, output_file)
    finally:
        if temp_output.exists():
            temp_output.unlink()
        if inspect_sidecar.exists():
            inspect_sidecar.unlink()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-root", type=Path, default=CLIENT_ROOT)
    parser.add_argument("--master", type=Path, default=MASTER_FILE)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--no-ocr", action="store_true", help="Do not OCR image-only candidate PDFs")
    parser.add_argument("--payload", type=Path, help="Optional JSON payload output for diagnostics")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.client_root, args.master, allow_ocr=not args.no_ocr)
    if args.payload:
        args.payload.parent.mkdir(parents=True, exist_ok=True)
        args.payload.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_workbook(payload, args.output)
    print(f"Workbook: {args.output}")
    print(f"Companies: {len(payload['sheets'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"ERROR: {error}") from error
