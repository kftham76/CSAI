from pathlib import Path
from pypdf import PdfReader
import pandas as pd
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
import hashlib
import json
import os
import re
import shutil
import sys
import time
import warnings
from datetime import datetime
import sqlite3

# Optional OCR support for scanned PDFs. RapidOCR is the preferred backend
# because it does not require a separately installed Tesseract executable.
OCR_BACKEND = ""
_OCR_ENGINE = None
_OCR_CACHE = {}

try:
    import numpy as np
    import pypdfium2
    from rapidocr_onnxruntime import RapidOCR
    OCR_BACKEND = "rapidocr"
    OCR_AVAILABLE = True
except ImportError:
    try:
        import pytesseract
        from pdf2image import convert_from_path
        pytesseract.get_tesseract_version()
        OCR_BACKEND = "tesseract"
        OCR_AVAILABLE = True
    except (ImportError, OSError, FileNotFoundError):
        OCR_AVAILABLE = False

# Suppress pypdf warnings (multiple categories emitted by pypdf internals)
warnings.filterwarnings("ignore", module="pypdf")
warnings.filterwarnings("ignore", category=UserWarning)

CLIENT_ROOT = Path(os.environ.get("CSAI_CLIENT_ROOT", r"D:\CSAI_CLIENTS"))
OUTPUT_FILE = Path(
    os.environ.get(
        "CSAI_OUTPUT_FILE",
        r"D:\CSAI_DATA\Database\clients_master.xlsx",
    )
)
DB_DIR = Path(
    os.environ.get(
        "CSAI_DB_DIR",
        r"C:\CSAI_OS\04 Python Tools\DB",
    )
)
CLIENT_FILTER_PATTERN = os.environ.get("CSAI_CLIENT_FILTER_REGEX", "").strip()
DOCUMENT_READER_VERSION = "event-ledger-v3"
SUPPORTED_SECTIONS = {"S14", "S51", "S58", "S68", "S78", "FORM49"}
SECTION_PRECEDENCE = {
    "S14": 10,
    "FORM49": 15,
    "S68": 20,
    "S51": 30,
    "S58": 40,
    "S78": 40,
}
EXCLUDED_STATE_SOURCE = re.compile(
    r"(?i)(?:^|[\\/ _-])"
    r"(draft|receipt|invoice|authority|confirmation|email|gmail|"
    r"resolution|dwr|mwr|bill)"
    r"(?:$|[\\/ _().-])"
)
PREFERRED_STATE_SOURCE = re.compile(
    r"(?i)(approved|approval|lodged|registered|certified|ctc)"
)

DIRECTOR_OUTPUT_FIELDS = (
    ("Name", "Name"),
    ("IC", "IC"),
    ("ID Type", "ID Type"),
    ("DOB", "DOB"),
    ("Passport Expiry", "Passport Expiry"),
    ("Nationality", "Nationality"),
    ("Citizenship", "Citizenship"),
    ("Race", "Race"),
    ("Gender", "Gender"),
    ("Designation", "Designation"),
    ("Business Occupation", "Business Occupation"),
    ("Residential Address", "Residential"),
    ("Service Address", "Service Address"),
    ("Email", "Email"),
    ("Contact No", "Contact No"),
    ("Appointment Date", "Appointment Date"),
)


####################################################
# PDF READER
####################################################

def read_pdf(pdf):
    """Read PDF text, suppressing pypdf's stderr noise from C extension."""

    text = ""

    try:
        # Redirect stderr to devnull to suppress pypdf's C-level warnings
        import os
        old_stderr = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        os.close(devnull)

        reader = PdfReader(pdf)

        for page in reader.pages:

            t = page.extract_text()

            if t:
                text += "\n" + t

        # Restore stderr
        os.dup2(old_stderr, 2)
        os.close(old_stderr)

    except Exception as e:

        print("PDF ERROR :", pdf)
        print(e)

        # Ensure stderr restored even on error
        try:
            os.dup2(old_stderr, 2)
            os.close(old_stderr)
        except:
            pass

    # Normalize non-breaking spaces — PdfReader emits \xa0, but Python \s
    # does not match \xa0, breaking regex patterns.
    text = text.replace("\xa0", " ")

    return text


####################################################
# CLEAN
####################################################

def clean(text):

    if not text:
        return ""

    # Process per line to preserve word boundaries (newlines separate words)
    lines = text.split("\n")
    out = []
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        line = line.replace("\xad", "")  # remove soft hyphens
        if not line:
            continue

        # Pass 1: pure uppercase — B U K I T -> BUKIT, T A M A N -> TAMAN
        line = re.sub(
            r'\b(?:[A-Z]\s){2,}[A-Z]\b',
            lambda m: m.group(0).replace(" ", ""),
            line
        )
        # Pass 2: mixed chars (digits, periods, hyphens) — N O . 3 A , -> NO.3A,
        #          0 8 0 0 0 -> 08000,   5 2 A - 1 , -> 52A-1,
        line = re.sub(
            r'\b(?:[A-Z0-9.\-]\s){2,}[A-Z0-9.,](?=\s|$)',
            lambda m: m.group(0).replace(" ", ""),
            line
        )

        out.append(line)

    return " ".join(out)


####################################################
# COMPANY NAME
####################################################

def company_name(text):

    patterns = [

        r'Name of company\s+(.*?)\s+Former name',

        r'Name of company\s+(.*?)\s+Goods and Services Tax',

        r'Proposed name\s+(.*?)\s+Lodging Reference No',

        r'Proposed name\s+(.*?)\s+Purpose',

    ]

    for p in patterns:

        m = re.search(
            p,
            text,
            re.I | re.S
        )

        if m:
            return clean(m.group(1))

    return ""


####################################################
# REG NO
####################################################

def reg_no(text):

    new_no = ""
    old_no = ""

    ############################################
    # SECTION 58
    ############################################

    m = re.search(
        r'''
        Registration\s*No\.?
        \s*
        (\d{12})
        \s*
        \(
        ([^)]+)
        \)
        ''',
        text,
        re.I | re.S | re.X
    )

    if m:

        return (
            f"{m.group(1)} "
            f"({m.group(2).strip()})"
        )

    ############################################
    # SECTION 68
    ############################################

    m = re.search(
        r'''
        New\s+Company\s+
        registration\s+number
        \s+
        (\d{12})
        ''',
        text,
        re.I | re.S | re.X
    )

    if m:
        new_no = m.group(1)

    #
    # IMPORTANT:
    # exclude "New Company registration number"
    #

    m = re.search(
        r'''
        (?<!New\s)
        Company\s+
        registration\s+number
        \s+
        ([0-9A-Z\-]+)
        ''',
        text,
        re.I | re.S | re.X
    )

    if m:
        old_no = m.group(1)

    ############################################

    if old_no:

        old_no = old_no.strip()

        if old_no == new_no:
            old_no = ""

    ############################################

    if new_no and old_no:
        return f"{new_no} ({old_no})"

    elif new_no:
        return new_no

    elif old_no:
        return old_no

    return ""

####################################################
# ANNUAL RETURN DATE
####################################################

def annual_return_date(text):

    patterns = [

        r'Date of annual return\s+(\d{4}-\d{2}-\d{2})',

        r'Submission Date\s+(\d{2}/\d{2}/\d{4})',

        r'Annual Return Date\s+(\d{2}/\d{2}/\d{4})'
    ]

    for p in patterns:

        m = re.search(
            p,
            text,
            re.I
        )

        if m:

            d = m.group(1)

            try:

                if "-" in d:

                    dt = datetime.strptime(
                        d,
                        "%Y-%m-%d"
                    )

                    return dt.strftime(
                        "%d/%m/%Y"
                    )

                return d

            except:
                pass

    return ""


####################################################
# BUSINESS ADDRESS
####################################################

def business_address(text):

    patterns = [

        r'''
        Address\splace\sof\sbusiness
        .*?
        0001
        (.*?)
        Company\sNo
        ''',

        r'''
        Address\sof\splace\sof\sbusiness
        (.*?)
        Address\sof\sfinancial
        '''
    ]

    for p in patterns:

        m = re.search(
            p,
            text,
            re.I | re.S | re.X
        )

        if m:

            return clean(
                m.group(1)
            )

    return ""


####################################################
# FINANCIAL ADDRESS
####################################################

def financial_address(text):

    # Old format (2021-2023):
    # "Address of financial records are kept
    #  Address line 1 NO.3355...
    #  Address of principal place of business"
    m = re.search(
        r'Address\s*of\s*financial\s*records\s*are\s*kept\s*'
        r'(.*?)\s*'
        r'Address\s*of\s*principal\s*place\s*of\s*business',
        text, re.I | re.S
    )
    if m:
        return clean(m.group(1))

    # New format (2024+):
    # "Address of financial records are kept
    #  No Address
    #  0001 [actual address]
    #  Address place of business"
    m = re.search(
        r'Address\s*of\s*financial\s*records\s*are\s*kept\s*'
        r'(.*?)\s*'
        r'Address\s*place\s*of\s*business',
        text, re.I | re.S
    )
    if m:
        captured = m.group(1)
        if re.search(r'No\s*Address', captured, re.I):
            m2 = re.search(r'0001\s+(.*)', captured, re.I | re.S)
            if m2:
                return clean(m2.group(1))
            return ""
        return clean(captured)

    return ""


####################################################
# DATE HELPERS
####################################################

def parse_date(d):
    """Parse supported SSM date formats to a datetime."""
    if isinstance(d, datetime):
        return d
    value = str(d or "").strip()
    for date_format in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    return None


def extract_submission_date(text):
    """Get an explicit submission/lodgement date from an SSM document."""
    patterns = [
        r'(?:Submission|Submitted)\s+Date\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})',
        r'Date\s+of\s+Lodgement\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})',
        r'Date\s+of\s+Submission\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})',
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            d = m.group(1)
            dt = parse_date(d)
            return dt.strftime("%d/%m/%Y") if dt else d
    return ""


def extract_ref_date(text):
    """Extract the encoded lodgement date from a known SSM reference."""
    m = re.search(
        r'(?:ROM|CPO|ROA|XBAR|CIU[-\s]*COU)\s*(\d{2})(\d{2})(\d{4})',
        text,
        re.I
    )
    if m:
        value = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        return value if parse_date(value) else ""
    return ""


def extract_total_shares(text):
    m = re.search(r'TOTAL NUMBER OF SHARES\s+([\d,]+)', text, re.I)
    if m:
        return m.group(1).replace(",", "")
    m = re.search(
        r'Total number of\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+([\d,]+)\s+shares issued',
        text, re.I
    )
    if m:
        return m.group(1).replace(",", "")
    return ""


def extract_total_shares_s51(text):
    m = re.search(r'Total Issued Shares\s*:?\s*([\d,]+)', text, re.I)
    if m:
        return m.group(1).replace(",", "")
    return ""


def extract_cessation_section58(text):
    if "DIRECTOR" not in text.upper():
        return None
    m = re.search(
        r'SECTION\s+C\s*:\s*CESSATION\s+OF\s+DIRECTOR\s+(.*?)'
        r'(?:SECTION|PARTICULARS\s+OF\s+LODGER)',
        text, re.I | re.S
    )
    if not m:
        return None
    block = m.group(1)
    result = {}
    ic_m = re.search(r'Identification\s+Number\s+(\d{12})', block)
    if ic_m: result["IC"] = ic_m.group(1)
    name_m = re.search(r'Name\s+(.*?)(?:\n|$)', block)
    if name_m: result["Name"] = clean(name_m.group(1))
    date_m = re.search(r'Date of Cessation\s+(\d{2}/\d{2}/\d{4})', block)
    if date_m: result["Date of Cessation"] = date_m.group(1)
    reason_m = re.search(r'Cessation Reason\s+(.*?)(?:\n|$)', block)
    if reason_m: result["Cessation Reason"] = reason_m.group(1).strip()
    return result if result else None


def find_all_section58(folder):
    results = []
    for pdf in folder.rglob("*.pdf"):
        name = pdf.name.lower()
        if "section 58" not in name and "sec58" not in name:
            continue
        text = read_pdf(pdf)
        if "DIRECTOR" not in text.upper():
            continue
        d = extract_submission_date(text)
        if not d:
            d = extract_ref_date(text)
        if not d:
            m = re.search(r'Date\s+Of\s+Appointment\s+(\d{2}/\d{2}/\d{4})', text, re.I)
            if m: d = m.group(1)
        if not d:
            m = re.search(r'Date of Cessation\s+(\d{2}/\d{2}/\d{4})', text, re.I)
            if m: d = m.group(1)
        if not d:
            continue
        dt = parse_date(d)
        if not dt:
            continue
        results.append((pdf, text, d, dt))
    results.sort(key=lambda x: x[3])
    return results


####################################################
# SECTION 51 — MEMBER / SHAREHOLDER DATA
####################################################

def find_latest_section51(folder):
    """Find the latest Section 51 (Register of Members) PDF in folder.
    Returns (pdf_path, date_str, date_dt) or (None, None, None)."""

    latest_pdf = None
    latest_dt = None
    latest_str = ""

    for pdf in folder.rglob("*.pdf"):

        name = pdf.name.lower()

        if "section 51" not in name and "sec51" not in name:
            continue

        text = read_pdf(pdf)

        d = extract_submission_date(text)

        if not d:
            d = extract_ref_date(text)

        if not d:
            continue

        dt = parse_date(d)

        if not dt:
            continue

        if latest_dt is None or dt > latest_dt:
            latest_dt = dt
            latest_str = d
            latest_pdf = pdf

    return latest_pdf, latest_str, latest_dt


def should_use_section51(section51_date, base_date, members):
    """Section 51 replaces member data only when it is strictly newer."""
    if not members:
        return False
    if base_date is None:
        return section51_date is not None
    return section51_date is not None and section51_date > base_date


def extract_members_section51(text):
    """Extract member data from Section 51 Register of Members."""

    members = []

    #
    # Find shareholders section
    #

    m = re.search(
        r'PARTICULAR\s+OF\s+SHAREHOLDERS\s+(.*?)'
        r'(?:ANALYSIS\s+OF\s+SHAREHOLDINGS|DECLARATION)',
        text,
        re.I | re.S
    )

    if not m:
        return members

    block = m.group(1)

    #
    # Split by share data lines: each member record ends with share numbers
    # Pattern: "shares_in shares_out total_shares date"
    #

    chunks = re.split(
        r'(\d[\d,]*[ \t]+\d[\d,]*[ \t]+\d[\d,]*[ \t]+\d[\d,]*(?:[ \t]+\d{2}/\d{2}/\d{4})?)',
        block
    )

    for i in range(1, len(chunks), 2):

        data_line = chunks[i]
        preceding = chunks[i - 1].strip()

        if len(preceding) < 20:
            continue

        #
        # Extract optional trailing date, remove it before number parsing
        #

        member_date = ""
        date_m = re.search(r'(\d{2}/\d{2}/\d{4})\s*$', data_line)
        if date_m:
            member_date = date_m.group(1)
            data_line = data_line[:date_m.start()].strip()

        #
        # Parse preceding block for ID, Name, Address
        # PDF text often splits every word into its own line, so
        # we collect all non-header lines into one text block then
        # detect the boundary between name and address.
        #

        lines = [
            l.strip() for l in preceding.split("\n")
            if l.strip()
        ]

        member_id = ""

        #
        # Header keywords: skip these during ID detection
        #
        header_keywords = [
            "IDENTIFICATION", "SHAREHOLDERS", "NAME", "ADDRESS",
            "NUMBER OF", "TRANSFER", "CESSATION", "UPDATE",
            "PROFILE", "TOTAL", "FINAL", "SHARES", "DATE OF",
            "PARTICULAR", "NO OF"
        ]

        #
        # Pre-process: merge lines connected by soft hyphen (\xad).
        # PDF text extraction splits "870721‑02‑5451" as "870721‑02‑\n5451".
        #
        merged_lines = []
        carry = ""
        for line in lines:
            if carry:
                line = carry + line
                carry = ""
            if line.rstrip().endswith("\xad"):
                carry = line.rstrip()  # keep trailing \xad, will merge with next
                continue
            merged_lines.append(line)
        if carry:
            merged_lines.append(carry)
        lines = merged_lines

        # Phase 1: scan lines to find the ID (skip headers).
        # Records (id_index, id_line_remainder) so Phase 2 can use
        # the original lines list without destructive modification.
        id_index = -1
        id_line_remainder = ""
        for idx, line in enumerate(lines):
            stripped = line.strip()
            upper = stripped.upper()

            # Skip header rows
            if any(hw in upper for hw in header_keywords):
                continue

            # Skip lines that are just punctuation/numbers (reference noise)
            if re.match(r'^[\d\s\-\.\,\#\/\(\)]+$', stripped) and len(stripped) < 8:
                continue

            words = stripped.split()
            condensed = re.sub(r"[\s\xad]", "", stripped)
            word_count = len(words)

            if word_count == 1:
                # Single word — try whole-line ID patterns

                # --- Pattern A: 12-digit IC ---
                if re.match(r'^\d{12}$', condensed):
                    member_id = condensed
                    id_index = idx
                    break

                # --- Pattern B: pure digits, 6+ chars (passport number) ---
                if re.match(r'^\d{6,20}$', condensed):
                    member_id = condensed
                    id_index = idx
                    break

                # --- Pattern C: alphanumeric ID ---
                if re.match(r'^[\dA-Z\-]{4,30}$', condensed) and re.search(r'\d', condensed):
                    member_id = condensed
                    id_index = idx
                    break
            else:
                # Multi-word — try Pattern D: first word is ID, rest is name
                first_condensed = re.sub(r"[\s\xad]", "", words[0])
                if re.match(r'^[\dA-Za-z\-]{4,20}$', first_condensed) and re.search(r'\d', first_condensed):
                    member_id = first_condensed
                    id_index = idx
                    id_line_remainder = " ".join(words[1:])
                    break

        if not member_id or id_index < 0:
            continue

        #
        # Phase 2: collect all text AFTER the ID line onward
        #
        info_lines = []
        if id_line_remainder:
            info_lines.append(id_line_remainder)
        for line in lines[id_index + 1:]:
            stripped = line.strip()
            info_lines.append(stripped)

        if not info_lines:
            continue

        info_text = " ".join(info_lines)

        #
        # Phase 3: split name from address in info_text
        # Strategy: detect where address starts by looking for
        # address markers (postcode, street prefixes, country)
        #

        # Try splitting at company suffix first
        # (everything after "SDN. BHD." / "BHD." / "LTD." is address)
        company_suffixes = [
            r'SDN\.?\s*BHD\.?',
            r'SDN\.?\s*BHD',
            r'BHD\.?',
            r'LTD\.?',
            r'LIMITED',
            r'INC\.?',
            r'CORPORATION',
            r'CO\.?\s*LTD\.?',
            r'PLC',
        ]

        name_end = len(info_text)
        for suf in company_suffixes:
            m = re.search(suf, info_text, re.I)
            if m:
                end_pos = m.end()
                # If there's more text after the suffix, split there
                if end_pos < len(info_text):
                    name_end = end_pos
                    break

        # If we found a company suffix, split name = text up to suffix end
        if name_end < len(info_text):
            name = clean(info_text[:name_end])
            address = clean(info_text[name_end:])
        else:
            # No company suffix — look for address indicators
            # Street/location prefixes that mark address start
            addr_starters = re.compile(
                r'\b(NO\.?\s+|LOT\s+|UNIT\s+|'
                r'JALAN\s+|LORONG\s+|PERSIARAN\s+|BANDAR\s+|'
                r'TAMAN\s+|KAMPUNG\s+|BUKIT\s+|LEBUH\s+|'
                r'DESA\s+|SUNGAI\s+|PULAU\s+|BATU\s+|'
                r'MUKIM\s+|DAERAH\s+|NEGERI\s+|'
                r'BLK\s+|BLOK\s+)',
                re.I
            )
            m = addr_starters.search(info_text)
            if m and m.start() > 3:  # address marker not at very start
                name = clean(info_text[:m.start()])
                address = clean(info_text[m.start():])
            else:
                # Fallback: split at postcode (5 digits)
                m = re.search(r'\b\d{5}\b', info_text)
                if m and m.start() > 3:
                    name = clean(info_text[:m.start()])
                    address = clean(info_text[m.start():])
                else:
                    # Last resort: everything except trailing country name
                    m = re.search(r'\b(MALAYSIA|SINGAPORE|TAIWAN|INDIA|CHINA)\s*$', info_text, re.I)
                    if m and m.start() > 3:
                        name = clean(info_text[:m.start()])
                        address = clean(info_text[m.start():])
                    else:
                        name = clean(info_text)
                        address = ""

        #
        # Extract shares numbers from data_line (date already removed)
        #

        nums = re.findall(r"[\d,]+", data_line)
        # 4 nums: [Number_of_Shares, Transferred_In, Transferred_Out, Total_Final]
        # 3 nums (fallback): [Transferred_In, Transferred_Out, Total_Final]
        if len(nums) >= 4:
            shares_total = nums[3]
            shares_in = nums[1]
            shares_out = nums[2]
        elif len(nums) >= 3:
            shares_total = nums[2]
            shares_in = nums[0]
            shares_out = nums[1]
        else:
            continue

        # Remove commas from numbers
        shares_total = shares_total.replace(",", "")
        shares_in = shares_in.replace(",", "")
        shares_out = shares_out.replace(",", "")

        #
        # Determine nationality/race from context (limited in Section 51)
        #

        nationality = ""
        race = ""

        if "MALAYSIA" in address.upper():
            nationality = "MALAYSIA"

        #
        # Detect corporate member type from name suffix
        #

        member_type = "INDIVIDUAL"
        name_upper = name.upper()
        if any(s in name_upper for s in [
            "SDN. BHD.", "SDN BHD", "SDN.BHD.", "BHD.",
            "LTD.", "PLC", "INC.", "LIMITED", "CORPORATION",
            "CO. LTD", "CO LTD", "COMPANY", "HOLDINGS",
        ]):
            member_type = "COMPANY"

        members.append({
            "IC": member_id,
            "Name": name,
            "Address": address,
            "Shares": shares_total,
            "Transferred In": shares_in,
            "Transferred Out": shares_out,
            "Date": member_date,
            "Nationality": nationality,
            "Race": race,
            "Type": member_type,
        })

    return members


####################################################
# SECTION 58 — DIRECTOR / SECRETARY CHANGES
####################################################

def find_latest_section58(folder):
    """Find the latest Section 58 (Notification of Change) PDF in folder."""

    latest_pdf = None
    latest_date = None

    for pdf in folder.rglob("*.pdf"):

        name = pdf.name.lower()

        if "section 58" not in name and "sec58" not in name:
            continue

        text = read_pdf(pdf)

        #
        # Check if this is a DIRECTOR change (not just secretary)
        #

        if "DIRECTOR" not in text.upper():
            continue

        #
        # Try various date sources
        #

        d = extract_submission_date(text)

        if not d:
            d = extract_ref_date(text)

        if not d:
            # Look for Date of Appointment
            m = re.search(
                r'Date\s+Of\s+Appointment\s+(\d{2}/\d{2}/\d{4})',
                text,
                re.I
            )
            if m:
                d = m.group(1)

        if not d:
            continue

        dt = parse_date(d)

        if not dt:
            continue

        if latest_date is None or dt > latest_date:
            latest_date = dt
            latest_pdf = pdf

    return latest_pdf


def extract_directors_section58(text):
    """Extract director data from Section 58 notification."""

    directors = []

    #
    # Check if it has director content
    #

    if "DIRECTOR" not in text.upper():
        return directors

    #
    # Find NEW DIRECTOR section
    #

    m = re.search(
        r'SECTION\s+[BC]\s*:\s*NEW\s+DIRECTOR\s+(.*?)'
        r'(?:SECTION|PARTICULARS\s+OF\s+LODGER)',
        text,
        re.I | re.S
    )

    if not m:
        return directors

    block = m.group(1)

    #
    # Extract fields
    #

    fields = {
        "Name": r'Name\s+(.*?)(?:\n|$)',
        "IC": r'Identification\s+Number\s+(\d{12})',
        "Nationality": r'Nationality\s+([A-Z]+)',
        "Race": r'Race\s+([A-Z]+)',
        "Gender": r'Gender\s+([A-Z]+)',
        "DOB": r'Date\s+of\s+Birth\s+(\d{2}/\d{2}/\d{4})',
        "Appointment Date": r'Date\s+Of\s+Appointment\s+(\d{2}/\d{2}/\d{4})',
    }

    director = {}

    for key, pattern in fields.items():
        fm = re.search(pattern, block, re.I)
        if fm:
            val = fm.group(1).strip()
            if key in ("Name",):
                val = clean(val)
            director[key] = val

    #
    # Residential Address
    #

    addr_m = re.search(
        r'Residential\s+Address\s+(.*?)(?:Service\s+Address|Email|$)',
        block,
        re.I | re.S
    )

    if addr_m:
        director["Residential"] = clean(addr_m.group(1))
    else:
        director["Residential"] = ""

    if director.get("Name"):
        directors.append(director)

    return directors


####################################################
# DIRECTORS
####################################################

def extract_directors(text):

    directors = []

    ################################################
    # SECTION 68
    ################################################

    m = re.search(

        r'''
        Particulars\sof\sDirectors
        (.*?)
        Particulars\sof\sManagers
        ''',

        text,

        re.I | re.S | re.X
    )

    if m:

        block = m.group(1)

        rows = re.split(
            r'\b000\d\b',
            block
        )

        for r in rows:

            r = clean(r)

            if not r:
                continue

            m2 = re.search(

                r'''
                (.+?)
                DIRECTOR
                \s+
                ([A-Z]+)
                \s+
                (\d+)

                (.*?)

                (MALAYSIA)
                \s+
                ([A-Z]+)
                \s+
                (MALE|FEMALE)
                \s+
                (\d{4}-\d{2}-\d{2})

                (.*)
                ''',

                r,

                re.I | re.S | re.X
            )

            if not m2:
                continue

            tail = clean(m2.group(9))

            ################################################
            # Residential Address
            ################################################

            residential = ""
            service_address = ""

            m3 = re.search(r'(.*?\bMALAYSIA\b)', tail, re.I | re.S)
            if not m3:
                m3 = re.search(r'(.*?\bINDIA\b)', tail, re.I | re.S)

            if m3:
                residential = clean(m3.group(1))
                remaining = tail[m3.end():].strip()
                m4 = re.search(r'(.*?\bMALAYSIA\b)', remaining, re.I | re.S)
                if m4:
                    service_address = clean(m4.group(1))
                else:
                    occ_m = re.search(r'\b(COMPANY\s+DIRECTOR|DIRECTOR|BUSINESSMAN|MANAGER|EMPLOYEE|SELF\s+EMPLOYED|RETIRED|HOUSEWIFE|STUDENT|PROFESSIONAL|CONSULTANT|CHARTERED\s+SECRETARY|NIL)\b', remaining, re.I)
                    svc_text = remaining[:occ_m.start()].strip() if occ_m else remaining.strip()
                    svc_compact = re.sub(r'\s+', '', svc_text)
                    email_m = re.search(r'[\w.+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', svc_compact, re.I)
                    if email_m:
                        service_address = email_m.group(0)

            directors.append({

                "Name":
                    clean(m2.group(1)),

                "IC":
                    m2.group(3),

                "Nationality":
                    m2.group(5),

                "Race":
                    m2.group(6),

                "Gender":
                    m2.group(7),

                "DOB":
                    m2.group(8),

                "Residential":
                    residential,

                "Service Address":
                    service_address,
            })

        if directors:
            return directors

    ################################################
    # SECTION 58
    ################################################

    rows = re.split(
        r'\b\d{4}\b',
        text
    )

    for r in rows:

        r = clean(r)

        if "DIRECTOR" not in r.upper():
            continue

        m2 = re.search(

            r'''
            (.+?)
            DIRECTOR
            .*?
            (\d{12})
            .*?
            (MALAYSIA)
            \s+
            ([A-Z]+)
            \s+
            (MALE|FEMALE)
            \s+
            (\d{4}-\d{2}-\d{2})
            (.*)
            ''',

            r,

            re.I | re.S | re.X
        )

        if not m2:
            continue

        tail = clean(m2.group(7))

        residential = ""

        m3 = re.search(

            r'''
            (
                .*?
                MALAYSIA
            )
            ''',

            tail,

            re.I | re.S | re.X
        )

        if m3:

            residential = clean(
                m3.group(1)
            )

        directors.append({

            "Name":
                clean(m2.group(1)),

            "IC":
                m2.group(2),

            "Nationality":
                m2.group(3),

            "Race":
                m2.group(4),

            "Gender":
                m2.group(5),

            "DOB":
                m2.group(6),

            "Residential":
                residential,

            "Service Address":
                "",
        })

    return directors


####################################################
# MEMBERS (SECTION E)
####################################################

def extract_members(text):
    """Extract member/shareholder list from Section 68 SECTION E."""

    members = []

    #
    # 1. Locate SECTION E block
    #

    start = text.upper().find("SECTION E")

    if start < 0:
        return members

    end = text.upper().find("SECTION F", start)

    if end < 0:
        end = len(text)

    block = text[start:end]

    #
    # Skip column header row(s), find first data line
    # Data starts with ref number "0001 0001"
    #

    data_start = re.search(
        r'\n(\d{4}\s+\d{4}\s+)',
        block
    )

    if not data_start:
        return members

    data = block[data_start.end():].strip()

    #
    # 2. Split into individual member records
    #

    chunks = re.split(
        r'(?:(?<=\n)|(?<=^))(?=\d{4}\s+\d{4}\s+)',
        data
    )

    for chunk in chunks:

        chunk = chunk.strip()

        if not chunk or len(chunk) < 30:
            continue

        #
        # Strip leading reference number "0001 0001"
        #

        chunk = re.sub(
            r'^\d{4}\s+\d{4}\s+',
            '',
            chunk
        )

        #
        # Truncate at TOTAL NUMBER OF SHARES line
        #

        total_m = re.search(
            r'TOTAL NUMBER OF SHARES',
            chunk,
            re.I
        )

        if total_m:
            chunk = chunk[:total_m.start()]

        #
        # Clean spaced-out text
        #

        cleaned = clean(chunk)

        #
        # Find DOB as anchor point
        #

        dob_m = re.search(
            r'(\d{2}/\d{2}/\d{4})',
            cleaned
        )

        if not dob_m:
            continue

        dob = dob_m.group(1)
        before_dob = cleaned[:dob_m.start()].strip()
        after_dob_raw = cleaned[dob_m.end():].strip()

        #
        # Gender
        #

        gender_m = re.search(
            r'\b(MALE|FEMALE)\b',
            before_dob,
            re.I
        )

        gender = gender_m.group(
            1
        ).upper() if gender_m else ""

        #
        # ID Type + Number (MYKAD/PASSPORT)
        #

        id_m = re.search(
            r'\b(MYKAD|PASSPORT|NRIC|IDENTIFICATION\s+CARD)\s+'
            r'([A-Z0-9\-]+)',
            before_dob,
            re.I
        )

        id_type = id_m.group(
            1
        ).upper() if id_m else ""

        id_no = id_m.group(2) if id_m else ""

        #
        # Member Type (first word)
        #

        type_m = re.match(
            r'(INDIVIDUAL|COMPANY|BODY\s+CORPORATE|NOMINEE)',
            cleaned,
            re.I
        )

        member_type = type_m.group(
            1
        ).upper() if type_m else ""

        #
        # Name: between Type and ID
        #

        name = ""

        if type_m and id_m:

            raw = cleaned[
                type_m.end():id_m.start()
            ].strip()

            name = clean(raw)

        #
        # Nationality & Race: text between ID and Gender
        #

        nr_text = before_dob

        if id_m:
            nr_text = before_dob[
                id_m.end():
            ].strip()

        if gender_m:
            g_pos = nr_text.find(
                gender_m.group(1)
            )

            if g_pos >= 0:
                nr_text = nr_text[
                    :g_pos
                ].strip()

        nr_words = nr_text.split()

        nationality = ""
        race = ""

        if len(nr_words) >= 2:
            nationality = nr_words[-2]
            race = nr_words[-1]
        elif len(nr_words) >= 1:
            nationality = nr_words[-1]

        #
        # After DOB: collapse spaced digits in number
        # "1 0 0 0 0 0" -> "100000"
        #

        after_dob = re.sub(
            r'(?<=\d)\s+(?=\d)',
            '',
            after_dob_raw
        )

        #
        # Address: everything up to MALAYSIA
        #

        address = ""

        addr_m = re.search(
            r'^(.+?MALAYSIA)',
            after_dob,
            re.I
        )

        if addr_m:
            address = clean(
                addr_m.group(1)
            )

        #
        # Shares / Share Type / Analysis
        #

        shares_count = ""
        shares_type = ""
        analysis = ""

        if addr_m:
            remainder = after_dob[
                addr_m.end():
            ].strip()
        else:
            remainder = after_dob

        #
        # remaining: "100000 ORDINARY SHARES CITIZENS..."
        #

        st_m = re.search(
            r'(\d[\d,]*)\s+'
            r'((?:\w+\s+)*?SHARES?)'
            r'\s+(.*)',
            remainder,
            re.I
        )

        if st_m:
            shares_count = st_m.group(1)
            shares_type = st_m.group(
                2
            ).strip()
            analysis = clean(
                st_m.group(3)
            )

        members.append({
            "Type": member_type,
            "Name": name,
            "ID Type": id_type,
            "ID No": id_no,
            "Nationality": nationality,
            "Race": race,
            "Gender": gender,
            "DOB": dob,
            "Address": address,
            "Shares": shares_count,
            "Share Type": shares_type,
            "Analysis": analysis
        })

    return members


####################################################
# SECTION 68 LAYOUT TABLES
####################################################

def _layout_pages(pdf_path):
    """Return page text with PDF column positions preserved."""
    try:
        return [
            page.extract_text(extraction_mode="layout") or ""
            for page in PdfReader(pdf_path).pages
        ]
    except (TypeError, ValueError, OSError):
        return []


def _layout_column_start(lines, label, minimum=0, occurrence=0):
    """Find a table-heading column without relying on one PDF width."""
    matches = []
    pattern = re.compile(label, re.I)
    for line in lines:
        for match in pattern.finditer(line):
            if match.start() >= minimum:
                matches.append(match.start())
    matches = sorted(set(matches))
    return matches[occurrence] if len(matches) > occurrence else None


def _slice_layout_line(line, starts):
    padded = line.ljust(max(starts.values()) + 2)
    ordered = sorted(starts.items(), key=lambda item: item[1])
    values = {}
    for index, (name, start) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else len(padded)
        values[name] = padded[start:end].strip()
    return values


def _scaled_layout_starts(starts, base_width, page_width):
    if not base_width or not page_width or base_width == page_width:
        return starts
    ratio = page_width / base_width
    return {
        key: (0 if start == 0 else round(start * ratio))
        for key, start in starts.items()
    }


def _affine_layout_starts(starts, line, anchor_patterns):
    anchors = []
    minimum = 0
    for key, pattern in anchor_patterns:
        match = re.search(pattern, line[minimum:], re.I)
        if not match or key not in starts:
            continue
        actual = minimum + match.start()
        anchors.append((starts[key], actual))
        minimum = actual + 1
    if len(anchors) < 2:
        return starts
    base_left, actual_left = anchors[0]
    base_right, actual_right = anchors[-1]
    if base_right == base_left:
        return starts
    scale = (actual_right - actual_left) / (base_right - base_left)
    offset = actual_left - (scale * base_left)
    return {
        key: (0 if start == 0 else round((scale * start) + offset))
        for key, start in starts.items()
    }


def _director_page_starts(starts, lines):
    row = next(
        (line for line in lines if re.match(r"\s*\d{4}\b", line)),
        "",
    )
    if not row:
        return starts
    return _affine_layout_starts(
        starts,
        row,
        (
            ("designation", r"\bDIRECTOR\b"),
            ("identity", r"\b(?:MYKAD|NRIC|PASSPORT)\b"),
            ("nationality", r"\b(?:MALAYSIA|CHINA|INDIA|SINGAPORE)\b"),
            ("gender", r"\b(?:MALE|FEMALE)\b"),
            ("dob", r"\b\d{4}-\d{2}-\d{2}\b"),
        ),
    )


def _member_page_starts(starts, lines):
    row = next(
        (
            line for line in lines
            if re.match(r"\s*\d{4}\s+\d{4}\b", line)
        ),
        "",
    )
    if not row:
        return starts
    calibrated = _affine_layout_starts(
        starts,
        row,
        (
            ("member_type", r"\b(?:INDIVIDUAL|BODY\s+CORPORATE|COMPANY)\b"),
            ("identity", r"\b(?:MYKAD|NRIC|PASSPORT)\b"),
            ("nationality", r"\b(?:MALAYSIA|CHINA|INDIA|SINGAPORE)\b"),
            ("gender", r"\b(?:MALE|FEMALE)\b"),
            ("dob", r"\b\d{2}/\d{2}/\d{4}\b"),
            ("analysis", r"\b(?:CITIZENS|NON\s*-?\s*CITIZENS)\b"),
        ),
    )
    number_matches = list(re.finditer(r"\d{4}", row))
    member_type = re.search(
        r"\b(?:INDIVIDUAL|BODY\s+CORPORATE|COMPANY)\b", row, re.I
    )
    identity = re.search(r"(?:MYKAD|NRIC|PASSPORT)", row, re.I)
    nationality = re.search(
        r"\b(?:MALAYSIA|CHINA|INDIA|SINGAPORE)\b", row, re.I
    )
    gender = re.search(r"\b(?:MALE|FEMALE)\b", row, re.I)
    dob = re.search(r"\b\d{2}/\d{2}/\d{4}\b", row)
    analysis = re.search(r"\b(?:CITIZENS|NON\s*-?\s*CITIZENS)\b", row, re.I)
    if len(number_matches) >= 2:
        calibrated["reference"] = number_matches[1].start()
    if member_type:
        calibrated["member_type"] = member_type.start()
        name_match = re.search(r"\S", row[member_type.end():])
        if name_match:
            calibrated["name"] = member_type.end() + name_match.start()
    if identity:
        calibrated["identity"] = identity.start()
    if nationality:
        calibrated["nationality"] = nationality.start()
    if gender:
        calibrated["gender"] = gender.start()
    if dob:
        calibrated["dob"] = dob.start()
        address_match = re.search(r"\S", row[dob.end():])
        if address_match:
            calibrated["address"] = dob.end() + address_match.start()
    if analysis:
        calibrated["analysis"] = analysis.start()
        share_candidates = list(re.finditer(
            r"\d(?:\s{1,2}\d)+|\d+",
            row[calibrated.get("address", 0):analysis.start()],
        ))
        if share_candidates:
            calibrated["shares"] = (
                calibrated.get("address", 0) + share_candidates[-1].start()
            )
    return calibrated


def _collapse_spaced_glyphs(value):
    output = []
    run = []

    def flush_run():
        if not run:
            return
        output.append("".join(run) if len(run) >= 2 else run[0])
        run.clear()

    for token in value.split():
        if re.fullmatch(r"[A-Z0-9]", token, re.I):
            run.append(token)
        else:
            flush_run()
            output.append(token)
    flush_run()
    return " ".join(output)


def _clean_layout_value(parts):
    value = " ".join(str(part).strip() for part in parts if str(part).strip())
    value = _collapse_spaced_glyphs(value)
    value = re.sub(r"\s+", " ", value).strip()
    replacements = {
        "GEORGETOW N": "GEORGETOWN",
        "CONDOMINI UM": "CONDOMINIUM",
        "ENTREPRENE URS": "ENTREPRENEURS",
        "W. P.": "W.P.",
    }
    for old, new in replacements.items():
        value = re.sub(re.escape(old), new, value, flags=re.I)
    return value


def _clean_layout_address(parts):
    value = _clean_layout_value(parts).strip(" ,")
    value = re.split(
        r"\b(?:Company\s+No\s*:|Page\s+\d+\s+of\s+\d+|DIRECTOR)\b",
        value,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" ,")
    value = re.sub(r"(?<=\d)(?=[A-Z])", " ", value)
    value = re.sub(r"\b(\d)(\d{5})\b", r"\1 \2", value)
    replacements = {
        "CASAIDAMAN": "CASA IDAMAN",
        "DESAUNIVERSITI": "DESA UNIVERSITI",
        "GEORGETOWNPULAU": "GEORGETOWN PULAU",
        "GELUGORPULAU": "GELUGOR PULAU",
        "HAMBIR": "GAMBIR",
        "PULAU INANG": "PULAU PINANG",
        "ULAU INANG": "PULAU PINANG",
    }
    for old, new in replacements.items():
        value = re.sub(re.escape(old), new, value, flags=re.I)
    value = re.sub(r"\bALAYSIA\b", "MALAYSIA", value, flags=re.I)
    value = re.sub(r"\s+,", ",", value)
    return re.sub(r"\s+", " ", value).strip()


def _repair_member_identities_by_address(members):
    """Use a clean duplicate share-class row to repair a shifted identity row."""
    donors = {}
    for member in members:
        identifier = normalize_identifier(member.get("ID No", ""))
        address = normalize_person_name(member.get("Address", ""))
        if re.fullmatch(r"\d{12}", identifier) and address:
            donors[address] = member
    identity_fields = (
        "Type", "Name", "ID Type", "ID No", "Passport Expiry",
        "Nationality", "Race", "Gender", "DOB",
    )
    for member in members:
        identifier = normalize_identifier(member.get("ID No", ""))
        if re.fullmatch(r"\d{12}", identifier):
            continue
        donor = donors.get(normalize_person_name(member.get("Address", "")))
        if donor:
            for field in identity_fields:
                member[field] = donor.get(field, "")
    return members


def _split_layout_identity(value):
    value = _clean_layout_value([value])
    match = re.search(
        r"\b(MYKAD|NRIC|PASSPORT(?:\s+NUMBER)?|COMPANY\s+REGISTRATION)\b\s*(.*)",
        value,
        re.I,
    )
    if not match:
        return "", normalize_identifier(value)
    id_type = match.group(1).upper()
    if id_type.startswith("PASSPORT"):
        id_type = "PASSPORT"
    return id_type, normalize_identifier(match.group(2))


def _split_layout_nationality_race(value):
    value = _clean_layout_value([value])
    upper = value.upper()
    if upper.startswith("MALAYSIA"):
        return "MALAYSIA", value[len("MALAYSIA"):].strip()
    if upper.startswith("MALAYSIAN"):
        return "MALAYSIA", value[len("MALAYSIAN"):].strip()
    foreigner = re.match(r"(.+?\))\s+FOREIGNER(?:\s+(.*))?$", value, re.I)
    if foreigner:
        return foreigner.group(1).strip(), (foreigner.group(2) or "").strip()
    words = value.split()
    return (words[0], " ".join(words[1:])) if words else ("", "")


def _valid_layout_address(value):
    return not re.search(
        r"Company\s+No\s*:|Page\s+\d+\s+of\s+\d+|Particulars\s+of",
        value,
        re.I,
    )


def extract_directors_section68_layout(pages):
    """Parse Section D by table columns, carrying rows across page breaks."""
    directors = []
    in_table = False
    starts = None
    base_width = None
    active = None

    def flush():
        nonlocal active
        if not active:
            return
        values = {
            key: _clean_layout_value(parts)
            for key, parts in active.items()
        }
        name = values.get("name", "")
        designation = values.get("designation", "")
        id_type, identifier = _split_layout_identity(values.get("identity", ""))
        nationality, race = _split_layout_nationality_race(
            values.get("nationality", "")
        )
        residential = _clean_layout_address(active.get("residential", []))
        raw_service = _clean_layout_value(active.get("service", []))
        email_match = re.search(
            r"[\w.+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            raw_service,
            re.I,
        )
        email = email_match.group(0) if email_match else ""
        service = _clean_layout_address([
            raw_service[:email_match.start()] if email_match else raw_service
        ])
        if (
            name
            and "DIRECTOR" in designation.upper()
            and identifier
            and _valid_layout_address(residential)
            and _valid_layout_address(service)
        ):
            directors.append({
                "Name": name,
                "IC": identifier,
                "ID Type": id_type,
                "Passport Expiry": values.get("passport", ""),
                "Nationality": nationality,
                "Race": race,
                "Gender": values.get("gender", ""),
                "DOB": values.get("dob", ""),
                "Designation": designation,
                "Business Occupation": values.get("business", ""),
                "Residential": residential,
                "Service Address": service,
                "Email": email,
            })
        active = None

    for page in pages:
        lines = page.splitlines()
        page_width = max((len(value) for value in lines), default=base_width)
        scaled_starts = (
            _scaled_layout_starts(starts, base_width, page_width)
            if starts else None
        )
        page_starts = (
            (
                _director_page_starts(scaled_starts, lines)
                if page_width != base_width
                else scaled_starts
            )
            if starts
            else None
        )
        for line_index, line in enumerate(lines):
            if re.search(r"Particulars\s+of\s+Directors", line, re.I):
                in_table = True
                header = lines[line_index:line_index + 8]
                title_start = _layout_column_start(header, r"Title/Name")
                designation_start = _layout_column_start(header, r"Designation")
                identity_start = _layout_column_start(
                    header,
                    r"\bType\b",
                    minimum=(designation_start or 0) + 1,
                )
                passport_start = _layout_column_start(header, r"Passport")
                nationality_start = _layout_column_start(header, r"Nationality")
                gender_start = _layout_column_start(header, r"Gender")
                dob_start = _layout_column_start(header, r"Date\s+of\s+birth")
                residential_start = _layout_column_start(header, r"Residential")
                service_start = _layout_column_start(header, r"Service")
                business_start = _layout_column_start(header, r"Business")
                if all(value is not None for value in (
                    title_start, designation_start, identity_start, passport_start,
                    nationality_start, gender_start, dob_start, residential_start,
                    service_start, business_start,
                )):
                    starts = {
                        "number": 0,
                        "name": title_start,
                        "designation": designation_start,
                        "identity": identity_start,
                        "passport": passport_start,
                        "nationality": nationality_start,
                        "gender": gender_start,
                        "dob": dob_start,
                        "residential": residential_start,
                        "service": service_start,
                        "business": business_start,
                    }
                    base_width = max((len(value) for value in lines), default=0)
                    page_width = base_width
                    scaled_starts = starts
                    page_starts = starts
                continue
            if not in_table or not starts:
                continue
            if re.search(r"Particulars\s+of\s+Managers", line, re.I):
                flush()
                return directors
            if (
                not line.strip()
                or re.search(r"Company\s+No\s*:|Page\s+\d+\s+of\s+\d+", line, re.I)
                or re.search(r"Title/Name|Date\s+of\s+birth|expiry\s+date", line, re.I)
            ):
                continue
            number_match = re.match(r"\s*(\d{4})\b", line)
            if number_match:
                flush()
                active = {key: [] for key in starts if key != "number"}
                if page_width != base_width:
                    page_starts = _director_page_starts(scaled_starts, [line])
            if not active:
                continue
            sliced = _slice_layout_line(line, page_starts)
            for key in active:
                if sliced.get(key):
                    active[key].append(sliced[key])
    flush()
    return directors


def extract_members_section68_layout(pages):
    """Parse Section E members by layout columns, including continuation pages."""
    members = []
    in_table = False
    starts = None
    base_width = None
    active = None

    def flush():
        nonlocal active
        if not active:
            return
        values = {
            key: _clean_layout_value(parts)
            for key, parts in active.items()
        }
        id_type, identifier = _split_layout_identity(values.get("identity", ""))
        row_text = " ".join(
            part
            for parts in active.values()
            for part in parts
        )
        mykad_candidates = re.findall(r"(?<!\d)(\d{12})(?!\d)", row_text)
        if mykad_candidates:
            identifier = mykad_candidates[0]
            id_type = "MYKAD"
        name = values.get("name", "")
        leaked_digit = re.search(r"\s(\d)\s*$", name)
        if leaked_digit and re.fullmatch(r"\d{11}", identifier):
            identifier = leaked_digit.group(1) + identifier
            name = name[:leaked_digit.start()].strip()
            id_type = "MYKAD"
        nationality, race = _split_layout_nationality_race(
            values.get("nationality", "")
        )
        share_text = values.get("shares", "")
        share_match = re.match(r"([\d,]+)\s*(.*)", share_text)
        shares = share_match.group(1).replace(",", "") if share_match else ""
        share_type = share_match.group(2).strip() if share_match else ""
        address = _clean_layout_address(active.get("address", []))
        address_spill = re.search(r"\d+", share_type)
        if address_spill:
            spill = address_spill.group(0)
            if re.search(r"/\s", address):
                address = re.sub(r"/\s", f"/{spill} ", address, count=1)
            else:
                postcode_like = list(re.finditer(r"\b\d{4,5}\b", address))
                if postcode_like:
                    last = postcode_like[-1]
                    address = (
                        address[:last.end()] + spill + address[last.end():]
                    )
            address = _clean_layout_address([address])
        share_type_upper = share_type.upper()
        if "ORDINARY" in share_type_upper:
            share_type = "ORDINARY SHARES"
        elif "PREFERENCE" in share_type_upper or "FERENCE" in share_type_upper:
            share_type = "PREFERENCE SHARES"
        else:
            share_type = re.sub(r"\d+", "", share_type)
            share_type = re.sub(r"\s+", " ", share_type).strip()
        if (
            name
            and identifier
            and shares
            and _valid_layout_address(address)
        ):
            members.append({
                "Type": (
                    "INDIVIDUAL"
                    if values.get("member_type", "").upper().endswith("INDIVIDUAL")
                    else values.get("member_type", "")
                ),
                "Name": name,
                "ID Type": id_type,
                "ID No": identifier,
                "Passport Expiry": values.get("passport", ""),
                "Nationality": nationality,
                "Race": race,
                "Gender": values.get("gender", ""),
                "DOB": values.get("dob", ""),
                "Address": address,
                "Shares": shares,
                "Share Type": share_type,
                "Analysis": values.get("analysis", ""),
            })
        active = None

    for page in pages:
        lines = page.splitlines()
        page_width = max((len(value) for value in lines), default=base_width)
        scaled_starts = (
            _scaled_layout_starts(starts, base_width, page_width)
            if starts else None
        )
        page_starts = (
            (
                _member_page_starts(scaled_starts, lines)
                if page_width != base_width
                else scaled_starts
            )
            if starts
            else None
        )
        for line_index, line in enumerate(lines):
            if re.search(r"SECTION\s+E\s*:.*PARTICULARS\s+OF\s+MEMBERS", line, re.I):
                in_table = True
                header = lines[line_index:line_index + 10]
                reference_start = _layout_column_start(header, r"Reference")
                member_type_start = _layout_column_start(header, r"Type\s+of")
                title_start = _layout_column_start(header, r"Title/Name")
                identity_start = _layout_column_start(
                    header, r"Type/|Type\s*/Identification",
                    minimum=(title_start or 0) + 1,
                )
                passport_start = _layout_column_start(header, r"Passport")
                nationality_start = _layout_column_start(header, r"Nationality")
                gender_start = _layout_column_start(header, r"Gender")
                dob_start = _layout_column_start(header, r"Date\s+of\s+birth")
                address_start = _layout_column_start(header, r"Address")
                shares_start = _layout_column_start(
                    header,
                    r"Number\s+of",
                    minimum=(address_start or 0) + 1,
                )
                analysis_start = _layout_column_start(header, r"Analysis")
                if all(value is not None for value in (
                    reference_start, member_type_start, title_start, identity_start,
                    passport_start, nationality_start, gender_start, dob_start,
                    address_start, shares_start, analysis_start,
                )):
                    starts = {
                        "number": 0,
                        "reference": reference_start,
                        "member_type": member_type_start,
                        "name": title_start,
                        "identity": identity_start,
                        "passport": passport_start,
                        "nationality": nationality_start,
                        "gender": gender_start,
                        "dob": dob_start,
                        "address": address_start,
                        "shares": shares_start,
                        "analysis": analysis_start,
                    }
                    base_width = max((len(value) for value in lines), default=0)
                    page_width = base_width
                    scaled_starts = starts
                    page_starts = starts
                continue
            if not in_table or not starts:
                continue
            if re.search(r"TOTAL\s+NUMBER\s+OF\s+SHARES|SECTION\s+F", line, re.I):
                flush()
                return members
            if (
                not line.strip()
                or re.search(r"Company\s+No\s*:|Page\s+\d+\s+of\s+\d+", line, re.I)
                or re.search(r"Title/Name|Date\s+of\s+birth|expiry\s+date", line, re.I)
            ):
                continue
            number_match = re.match(r"\s*(\d{4})\s+\d{4}\b", line)
            if number_match:
                flush()
                active = {
                    key: []
                    for key in starts
                    if key not in {"number", "reference"}
                }
                if page_width != base_width:
                    page_starts = _member_page_starts(scaled_starts, [line])
            if not active:
                continue
            sliced = _slice_layout_line(line, page_starts)
            for key in active:
                if sliced.get(key):
                    active[key].append(sliced[key])
    flush()
    return members


def extract_section68_layout(pdf_path):
    pages = _layout_pages(pdf_path)
    if not pages:
        return [], []
    directors = extract_directors_section68_layout(pages)
    members = _repair_member_identities_by_address(
        extract_members_section68_layout(pages)
    )
    return directors, members


####################################################
# SECTION 14 — INCORPORATION APPLICATION (FALLBACK)
####################################################

def find_section14(folder):
    best_pdf = None
    best_text = None
    best_has_regno = False

    for pdf in folder.rglob("*.pdf"):
        text = read_pdf(pdf)
        is_section14 = is_section14_text(text)
        # Only OCR likely Section 14 files. Scanning every image-only PDF in a
        # client folder is both slow and likely to select an unrelated form.
        if not is_section14 and is_section14_filename(pdf.name) and OCR_AVAILABLE:
            ocr_text = try_ocr_pdf(pdf)
            is_section14 = is_section14_text(ocr_text)
            if is_section14:
                text = ocr_text
                print(f"  OCR used for {pdf.name}")
        if not is_section14:
            continue
        has_regno = bool(re.search(r'Registration No\.', text, re.I))
        if has_regno and not best_has_regno:
            best_pdf = pdf
            best_text = text
            best_has_regno = True
        elif not best_pdf:
            best_pdf = pdf
            best_text = text

    return best_pdf, best_text


def extract_company_section14(text):
    result = {
        "name": "", "reg_no": "",
        "business_address": "", "registered_address": "",
    }

    m = re.search(r'Proposed name:?\s*(.+?)(?:\n|$)', text, re.I)
    if m: result["name"] = clean(m.group(1))

    m = re.search(r'Registration No\.?:?\s*(.+?)(?:\n|$)', text, re.I)
    if m: result["reg_no"] = m.group(1).strip()

    m = re.search(r'Registered Address:?\s*(.+?)(?:\nEmail|\nOffice No|\nFax|$)', text, re.I | re.S)
    if m: result["registered_address"] = clean(m.group(1))

    m = re.search(r'Business Address:?\s*(.+?)(?:\nOffice No|\nFax|\nEmail|$)', text, re.I | re.S)
    if m: result["business_address"] = clean(m.group(1))

    return result


def extract_directors_section14(text):
    directors = []

    m = re.search(r'PARTICULARS OF DIRECTOR\s+(.*?)(?:PARTICULARS OF MEMBER|DECLARATION)', text, re.I | re.S)
    if not m:
        return directors

    block = m.group(1)
    entries = re.split(r'Director Name:?\s*', block)

    for entry in entries:
        if not entry.strip():
            continue

        director = {"Name": "", "IC": "", "Nationality": "", "Residential": "", "DOB": "", "Race": "", "Service Address": ""}

        name_m = re.search(r'^(.*?)(?:\n|$)', entry)
        if name_m: director["Name"] = clean(name_m.group(1))

        ic_m = re.search(r'Identification No\.?:?\s*(.+?)(?:\n|$)', entry, re.I)
        if ic_m: director["IC"] = ic_m.group(1).strip()

        nat_m = re.search(r'Nationality:?\s*(.+?)(?:\n|$)', entry, re.I)
        if nat_m: director["Nationality"] = nat_m.group(1).strip()

        addr_m = re.search(r'Address:?\s*(.+?)(?:\nDate of birth|\nRace|\nEmail|$)', entry, re.I | re.S)
        if addr_m: director["Residential"] = clean(addr_m.group(1))

        dob_m = re.search(r'Date of birth:?\s*(.+?)(?:\n|$)', entry, re.I)
        if dob_m: director["DOB"] = dob_m.group(1).strip()

        race_m = re.search(r'Race:?\s*(.+?)(?:\n|$)', entry, re.I)
        if race_m: director["Race"] = race_m.group(1).strip()

        email_m = re.search(r'Email:?\s*(.+?)(?:\n|$)', entry, re.I)
        if email_m: director["Service Address"] = email_m.group(1).strip()

        if director["Name"]:
            directors.append(director)

    return directors


def extract_members_section14(text):
    members = []

    m = re.search(r'PARTICULARS OF MEMBER\s+(.*?)(?:DECLARATION)', text, re.I | re.S)
    if not m:
        return members

    block = m.group(1)
    entries = re.split(r'Member Name:?\s*', block)

    for entry in entries:
        if not entry.strip():
            continue

        member = {"Name": "", "ID Type": "", "ID No": "", "Nationality": "", "Address": "", "Race": "", "Shares": "", "Share Type": ""}

        name_m = re.search(r'^(.*?)(?:\n|$)', entry)
        if name_m: member["Name"] = clean(name_m.group(1))

        id_m = re.search(r'ID Type:?\s*(.+?)(?:\n|$)', entry, re.I)
        if id_m: member["ID Type"] = id_m.group(1).strip()

        ic_m = re.search(r'Identification No\.?:?\s*(.+?)(?:\n|$)', entry, re.I)
        if ic_m: member["ID No"] = ic_m.group(1).strip()

        nat_m = re.search(r'Nationality:?\s*(.+?)(?:\n|$)', entry, re.I)
        if nat_m: member["Nationality"] = nat_m.group(1).strip()

        addr_m = re.search(r'Address:?\s*(.+?)(?:\nRace|\nEmail|\nPrice per share|\nNumber of share|$)', entry, re.I | re.S)
        if addr_m: member["Address"] = clean(addr_m.group(1))

        race_m = re.search(r'Race:?\s*(.+?)(?:\n|$)', entry, re.I)
        if race_m: member["Race"] = race_m.group(1).strip()

        shares_m = re.search(r'Number of share:?\s*([\d,]+)', entry, re.I)
        if shares_m: member["Shares"] = shares_m.group(1).replace(",", "")

        st_m = re.search(r'Class of share:?\s*(.+?)(?:\n|$)', entry, re.I)
        if st_m: member["Share Type"] = st_m.group(1).strip()

        if member["Name"]:
            members.append(member)

    return members


def extract_total_shares_section14(text):
    m = re.search(r'Total number of shares:?\s*([\d,]+)', text, re.I)
    if m:
        return m.group(1).replace(",", "")
    return ""


def extract_incorporation_date(text):
    m = re.search(
        r'Incorporation\s+Date\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})',
        text,
        re.I,
    )
    if m:
        return m.group(1).replace("-", "/")

    # Section 17 certificates use prose, including OCR variants such as
    # "8h day" where the ordinal suffix was only partly recognized.
    m = re.search(
        r'on\s+and\s+from\s+the\s+(\d{1,2})(?:st|nd|rd|th|h)?\s+day\s+of\s+'
        r'([A-Za-z]+)\s+(\d{4})\s*,?\s*incorporated',
        text,
        re.I,
    )
    if m:
        try:
            parsed = datetime.strptime(
                f"{m.group(1)} {m.group(2)} {m.group(3)}",
                "%d %B %Y",
            )
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            pass
    return ""


def is_section14_filename(name):
    name = name.lower()
    return bool(
        re.search(r'(?:section|sec)\s*14\b', name)
        or "superform 14" in name
    )


def is_section14_text(text):
    compact = re.sub(r'\s+', '', text).upper()
    return (
        "APPLICATIONFORREGISTRATIONOFACOMPANY" in compact
        or (
            "SECTION14" in compact
            and "PARTICULARSOFCOMPANY" in compact
        )
    )


def try_ocr_pdf(pdf_path, stop_when=None):
    """OCR a PDF with visible page progress and optional early termination."""
    if not OCR_AVAILABLE:
        return ""
    cache_key = str(Path(pdf_path).resolve())
    if cache_key in _OCR_CACHE:
        return _OCR_CACHE[cache_key]
    try:
        text_parts = []
        completed_all_pages = True
        if OCR_BACKEND == "rapidocr":
            global _OCR_ENGINE
            if _OCR_ENGINE is None:
                _OCR_ENGINE = RapidOCR()
            document = pypdfium2.PdfDocument(str(pdf_path))
            try:
                total_pages = len(document)
                print(
                    f"  OCR: {Path(pdf_path).name} ({total_pages} pages)",
                    flush=True,
                )
                for page_number, page in enumerate(document, start=1):
                    print(
                        f"    OCR page {page_number}/{total_pages}",
                        flush=True,
                    )
                    image = page.render(scale=2.5).to_pil()
                    result, _ = _OCR_ENGINE(np.asarray(image))
                    if result:
                        text_parts.extend(item[1] for item in result if len(item) > 1)
                    current_text = "\n".join(text_parts).replace("\xa0", " ")
                    if stop_when and stop_when(current_text):
                        completed_all_pages = page_number == total_pages
                        break
            finally:
                document.close()
        elif OCR_BACKEND == "tesseract":
            total_pages = len(PdfReader(pdf_path).pages)
            print(
                f"  OCR: {Path(pdf_path).name} ({total_pages} pages)",
                flush=True,
            )
            for page_number in range(1, total_pages + 1):
                print(
                    f"    OCR page {page_number}/{total_pages}",
                    flush=True,
                )
                images = convert_from_path(
                    str(pdf_path),
                    dpi=250,
                    first_page=page_number,
                    last_page=page_number,
                )
                if not images:
                    continue
                image = images[0]
                page_text = pytesseract.image_to_string(image)
                if page_text:
                    text_parts.append(page_text)
                current_text = "\n".join(text_parts).replace("\xa0", " ")
                if stop_when and stop_when(current_text):
                    completed_all_pages = page_number == total_pages
                    break
        text = "\n".join(text_parts).replace("\xa0", " ")
        if completed_all_pages:
            _OCR_CACHE[cache_key] = text
        return text
    except Exception as e:
        print(f"  OCR failed for {pdf_path.name}: {e}")
        _OCR_CACHE[cache_key] = ""
        return ""


def extract_section27_date(text):
    """Return the dated Section 27 event used to order name changes."""
    patterns = [
        r'Date\s+of\s+Application\s*:?\s*(\d{2}/\d{2}/\d{4})',
        r'Date\s+of\s+Lodgement\s*:?\s*(\d{2}/\d{2}/\d{4})',
        r'Submission\s+Date\s*:?\s*(\d{2}/\d{2}/\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return parse_date(match.group(1))

    # SSM name-reservation references encode DDMMYYYY after ACN.
    match = re.search(r'ACN\s*(\d{2})(\d{2})(\d{4})', text, re.I)
    if match:
        return parse_date(
            f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
        )
    return None


def extract_section27_new_name(text):
    patterns = [
        r'Proposed\s+Company\s+Name\s*:?\s*(.+?)(?:\n|$)',
        r'New\s+Company\s+Name\s*:?\s*(.+?)(?:\n|$)',
        r'New\s+Name\s*:?\s*(.+?)(?:\n|$)',
        r'Name\s+of\s+Company\s*:?\s*(.+?)(?:\n|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            name = clean(match.group(1))
            if name:
                return name
    return ""


def find_section27_new_name(folder):
    """Return the new name from the latest dated Section 27 document."""
    candidates = []
    for pdf in folder.rglob("*.pdf"):
        name = pdf.name.lower()
        if "section 27" not in name and "sec27" not in name:
            continue
        text = read_pdf(pdf)
        if "CHANGE OF NAME" not in text.upper() and "CHANGE OF COMPANY NAME" not in text.upper():
            continue
        event_date = extract_section27_date(text)
        new_name = extract_section27_new_name(text)
        if event_date and new_name:
            candidates.append((event_date, new_name, pdf))

    if not candidates:
        return ""

    latest_date = max(candidate[0] for candidate in candidates)
    latest = [candidate for candidate in candidates if candidate[0] == latest_date]
    latest_names = {candidate[1].upper(): candidate[1] for candidate in latest}
    if len(latest_names) > 1:
        names = ", ".join(sorted(latest_names.values()))
        print(f"  Section27 conflict on {latest_date:%d/%m/%Y}: {names}")
        return ""
    return next(iter(latest_names.values()))


def find_incorporation_date_in_folder(folder):
    """Find an incorporation date using the smallest, most specific document."""

    def candidate_rank(pdf):
        name = pdf.stem.lower()
        if re.search(r"(?:section|sec)\s*17\b", name):
            kind = 0
        elif re.fullmatch(r"\s*(?:section|sec)\s*14\s*", name):
            kind = 1
        elif "superform 14" in name:
            kind = 2
        else:
            kind = 3
        try:
            size = pdf.stat().st_size
        except OSError:
            size = sys.maxsize
        return kind, size, str(pdf).lower()

    candidates = []
    for pdf in folder.rglob("*.pdf"):
        name = pdf.name.lower()
        if any(
            keyword in name
            for keyword in (
                "section 14", "section 17", "sec14", "sec17",
                "superform 14",
            )
        ):
            candidates.append(pdf)

    for pdf in sorted(candidates, key=candidate_rank):
        text = read_pdf(pdf)
        incorporation_date = extract_incorporation_date(text)
        if incorporation_date:
            return incorporation_date
        if OCR_AVAILABLE:
            text = try_ocr_pdf(
                pdf,
                stop_when=lambda value: bool(extract_incorporation_date(value)),
            )
            incorporation_date = extract_incorporation_date(text)
            if incorporation_date:
                return incorporation_date
    return ""


####################################################
# LATEST SECTION68
####################################################

def latest_section68(folder):

    latest_pdf = None
    latest_date = None

    for pdf in folder.rglob("*.pdf"):

        text = read_pdf(pdf)

        if (
                "SECTION 68" not in text.upper()
                and
                "AR1" not in text.upper()
        ):
            continue

        d = annual_return_date(text)

        if not d:
            continue

        try:

            dt = datetime.strptime(
                d,
                "%d/%m/%Y"
            )

        except:
            continue

        if (
                latest_date is None
                or
                dt > latest_date
        ):

            latest_date = dt
            latest_pdf = pdf

    return latest_pdf


####################################################
# EVENT-AWARE STATUTORY DOCUMENT LEDGER
####################################################

def _json_default(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    raise TypeError(type(value).__name__)


def iso_date(value):
    return value.strftime("%Y-%m-%d") if isinstance(value, datetime) else ""


def parse_iso_date(value):
    return parse_date(value) if value else None


def parse_number(value, default=0):
    if value is None or value == "":
        return default
    normalized = re.sub(r"(?<=\d)\s+(?=[\d,])", "", str(value))
    normalized = re.sub(r"(?<=,)\s+(?=\d)", "", normalized)
    match = re.search(r"-?[\d,]+", normalized)
    if not match:
        return default
    try:
        return int(match.group(0).replace(",", ""))
    except ValueError:
        return default


def normalize_identifier(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def normalize_person_name(value):
    return re.sub(r"[^A-Z0-9]", "", clean(value).upper())


def normalize_registration_number(value):
    identifiers = registration_identifiers(value)
    return identifiers[0] if identifiers else ""


def registration_identifiers(value):
    text = str(value or "").upper()
    identifiers = []
    new_number = re.search(r"(?<!\d)(\d{12})(?!\d)", text)
    if new_number:
        identifiers.append(new_number.group(1))
    parenthetical = re.search(r"\(([^)]+)\)", text)
    if parenthetical:
        old_number = re.sub(r"[^A-Z0-9]", "", parenthetical.group(1))
        if old_number and old_number not in identifiers:
            identifiers.append(old_number)
    if not identifiers:
        primary = re.sub(r"[^A-Z0-9]", "", text.split("(", 1)[0])
        if primary:
            identifiers.append(primary)
    return identifiers


def person_key(person):
    identifier = normalize_identifier(
        person.get("ID No")
        or person.get("IC")
        or person.get("Identification Number")
    )
    if identifier:
        return f"ID:{identifier}"
    name = normalize_person_name(person.get("Name"))
    return f"NAME:{name}" if name else ""


def merge_nonempty(base, extra):
    result = deepcopy(base)
    numeric_zero_fields = {
        "Shares", "Transferred In", "Transferred Out",
        "Final Shares", "Allotted Shares",
    }
    for key, value in extra.items():
        if value not in (None, "") or key in numeric_zero_fields:
            result[key] = value
    return result


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_quality(path):
    value = str(path)
    if PREFERRED_STATE_SOURCE.search(value):
        return 3
    return 2


def date_from_filename(path):
    value = Path(path).stem
    candidates = []
    for year, month, day in re.findall(
        r"(?<!\d)(20\d{2})[-_ .]?([01]\d)[-_ .]?([0-3]\d)(?!\d)",
        value,
    ):
        parsed = parse_date(f"{year}-{month}-{day}")
        if parsed:
            candidates.append(parsed)
    for day, month, year in re.findall(
        r"(?<!\d)([0-3]\d)[-_ .]([01]\d)[-_ .](20\d{2})(?!\d)",
        value,
    ):
        parsed = parse_date(f"{day}/{month}/{year}")
        if parsed:
            candidates.append(parsed)
    month_numbers = {
        name: index
        for index, name in enumerate(
            (
                "january", "february", "march", "april", "may", "june",
                "july", "august", "september", "october", "november",
                "december",
            ),
            start=1,
        )
    }
    month_pattern = "|".join(month_numbers)
    for day, month_name, year in re.findall(
        rf"(?<!\d)([0-3]?\d)\s+({month_pattern})\s+(20\d{{2}})(?!\d)",
        value,
        re.I,
    ):
        parsed = parse_date(
            f"{int(day):02d}/{month_numbers[month_name.lower()]:02d}/{year}"
        )
        if parsed:
            candidates.append(parsed)
    return max(candidates) if candidates else None


def extract_lodgement_date(text, path=None):
    """Return (date, source) for a filing's best available lodgement date."""
    explicit = extract_submission_date(text)
    if explicit:
        return parse_date(explicit), "DOCUMENT"
    reference = extract_ref_date(text)
    if reference:
        return parse_date(reference), "REFERENCE"
    filename_date = date_from_filename(path) if path else None
    if filename_date:
        return filename_date, "FILENAME"
    return None, ""


def infer_section_from_path(path):
    # Use the filename, not parent folders. A file such as "section 17.pdf"
    # inside a "Section 14" directory must not be misclassified as S14.
    value = Path(path).name.lower()
    rules = (
        (r"(?:section|sec)[\s_-]*51(?!\d)|register[\s_-]*of[\s_-]*members?|\brom\b", "S51"),
        (r"(?:section|sec)[\s_-]*58(?!\d)|form[\s_-]*49(?!\d)", "S58"),
        (r"(?:section|sec)[\s_-]*78(?!\d)|form[\s_-]*24(?!\d)", "S78"),
        (r"(?:section|sec)[\s_-]*68(?!\d)|annual[\s_-]*return|\bar1\b", "S68"),
        (r"(?:section|sec)[\s_-]*14(?!\d)|super[\s_-]*form", "S14"),
    )
    for pattern, section in rules:
        if re.search(pattern, value, re.I):
            return section
    return ""


def classify_statutory_text(text):
    upper = clean(text).upper()
    if (
        re.search(r"\bSECTION\s*51(?!\d)", upper)
        and re.search(r"REGISTER\s+OF\s+MEMBERS?", upper)
    ):
        return "S51"
    if (
        re.search(r"\bSECTION\s*78(?!\d)", upper)
        and "RETURN OF ALLOTMENT" in upper
    ):
        return "S78"
    if (
        re.search(r"\bSECTION\s*58(?!\d)", upper)
        and ("NOTIFICATION OF CHANGE" in upper or "DIRECTOR" in upper)
    ):
        return "S58"
    if (
        re.search(r"\bSECTION\s*68(?!\d)", upper)
        and "ANNUAL RETURN" in upper
    ) or ("AR1" in upper and "ANNUAL RETURN" in upper):
        return "S68"
    if is_section14_text(text):
        return "S14"
    if re.search(r"\bFORM\s*24(?!\d)", upper) and (
        "ALLOTMENT" in upper or "SHARE" in upper
    ):
        return "S78"
    if re.search(r"\bFORM\s*49(?!\d)", upper) and (
        "DIRECTOR" in upper or "SECRETARY" in upper
    ):
        return "FORM49"
    return "OTHER"


def extract_document_registration_number(text):
    value = reg_no(text)
    if value:
        return value
    match = re.search(
        r"Registration\s*No\.?\s*:?\s*(\d{12})(?:\s*\(([^)]+)\))?",
        text,
        re.I,
    )
    if not match:
        registration_line = re.search(
            r"Registration\s*No\.?\s*:?\s*([^\n]+)",
            text,
            re.I,
        )
        if not registration_line:
            return ""
        value = registration_line.group(1)
        new_number = re.search(r"(?<!\d)(\d{12})(?!\d)", value)
        old_number = re.search(r"(?<![A-Z0-9])(\d{6,7}-[A-Z])(?![A-Z0-9])", value, re.I)
        if new_number and old_number:
            return f"{new_number.group(1)} ({old_number.group(1).upper()})"
        return new_number.group(1) if new_number else clean(value)
    return (
        f"{match.group(1)} ({match.group(2).strip()})"
        if match.group(2)
        else match.group(1)
    )


def extract_filing_reference(text):
    patterns = (
        r"(?:Lodging|Lodgement)\s+Reference\s+(?:Number|No\.?)\s*:?\s*([A-Z0-9-]+)",
        r"Reference\s+(?:Number|No\.?)\s*:?\s*([A-Z0-9-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return re.sub(r"\s+", "", match.group(1)).upper()
    return ""


def extract_section78_date(text):
    match = re.search(
        r"Date\s+of\s+Allotment\s*:?\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})",
        text,
        re.I,
    )
    return parse_date(match.group(1)) if match else None


def extract_total_shares_section78(text):
    matches = re.findall(
        r"Total\s+Accumulated\s+Issued(?:\s*\([^)]*\))?\s*:?\s*([\d,]+)",
        text,
        re.I,
    )
    values = [parse_number(value, None) for value in matches]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _member_identity_fields(identifier, name):
    normalized = normalize_identifier(identifier)
    upper_name = clean(name).upper()
    corporate = any(
        token in upper_name
        for token in (" SDN", " BHD", " LTD", " LIMITED", " CORPORATION", " PLC")
    )
    if corporate:
        return "BODY CORPORATE", "COMPANY REGISTRATION"
    if re.fullmatch(r"\d{12}", normalized):
        return "INDIVIDUAL", "MYKAD"
    return "INDIVIDUAL", "PASSPORT" if normalized else ""


def extract_allotments_section78(text):
    match = re.search(
        r"PARTICULAR\s+OF\s+ALLOTTEES\s+(.*?)(?:DECLARATION|LODGER\s+INFORMATION)",
        text,
        re.I | re.S,
    )
    if not match:
        return []
    block = clean(match.group(1))
    block = re.sub(
        r"^NO\s+ALLOTTEE\s+NAME.*?NO\s+OF\s+SHARE\s+",
        "",
        block,
        flags=re.I,
    )
    row_pattern = re.compile(
        r"(?:^|\s)(\d+)\s+"
        r"(?P<name>[A-Z][A-Z0-9 .&'()/@-]*?)\s+"
        r"(?P<identifier>(?:\d{6}\s*-?\s*\d{2}\s*-?\s*\d{4}|"
        r"\d{12}|[A-Z][A-Z0-9-]{4,30}))\s+"
        r"(?P<address>.+?)\s+"
        r"(?P<share_type>CASH|OTHERWISE)\s+"
        r"(?P<shares>[\d,]+)"
        r"(?=\s+\d+\s+[A-Z]|$)",
        re.I,
    )
    allotments = []
    for row in row_pattern.finditer(block):
        name = clean(row.group("name"))
        identifier = normalize_identifier(row.group("identifier"))
        member_type, id_type = _member_identity_fields(identifier, name)
        shares = parse_number(row.group("shares"))
        allotments.append({
            "Type": member_type,
            "Name": name,
            "ID Type": id_type,
            "ID No": identifier,
            "Nationality": "",
            "Race": "",
            "Gender": "",
            "DOB": "",
            "Address": clean(row.group("address")),
            "Shares": shares,
            "Allotted Shares": shares,
            "Share Type": "ORDINARY SHARES",
            "Analysis": "",
        })
    return allotments


def _section58_person_blocks(text, heading, end_heading):
    match = re.search(
        rf"{heading}\s+(.*?)(?:{end_heading}|PARTICULARS\s+OF\s+LODGER|$)",
        text,
        re.I | re.S,
    )
    if not match:
        return []
    return [
        block
        for block in re.split(
            r"(?=Identification\s+Number\s+[\d\s-]{10,20})",
            match.group(1),
            flags=re.I,
        )
        if re.search(r"Identification\s+Number", block, re.I)
    ]


def extract_all_appointments_section58(text):
    appointments = []
    blocks = _section58_person_blocks(
        text,
        r"SECTION\s+[A-Z]\s*:\s*NEW\s+DIRECTOR",
        r"SECTION\s+[A-Z]\s*:",
    )
    for block in blocks:
        fields = {}
        for key, pattern in (
            ("IC", r"Identification\s+Number\s+([\d\s-]{10,20})"),
            ("Name", r"Name\s+(.*?)(?:\n|$)"),
            ("DOB", r"Date\s+of\s+Birth\s+(\d{2}/\d{2}/\d{4})"),
            ("Gender", r"Gender\s+([A-Z]+)"),
            ("Race", r"Race\s+([A-Z]+)"),
            ("Nationality", r"Nationality\s+([A-Z]+)"),
            ("Appointment Date", r"Date\s+Of\s+Appointment\s+(\d{2}/\d{2}/\d{4})"),
        ):
            value_match = re.search(pattern, block, re.I)
            if value_match:
                fields[key] = clean(value_match.group(1))
        if fields.get("IC"):
            fields["IC"] = normalize_identifier(fields["IC"])
        address_match = re.search(
            r"Residential\s+Address\s+(.*?)(?:Service\s+Address|Email|$)",
            block,
            re.I | re.S,
        )
        if address_match:
            fields["Residential"] = clean(address_match.group(1))
        service_match = re.search(
            r"Service\s+Address\s+(.*?)(?:Email|$)",
            block,
            re.I | re.S,
        )
        if service_match:
            fields["Service Address"] = clean(service_match.group(1))
        if fields.get("Name") or fields.get("IC"):
            fields["Event Type"] = "APPOINT"
            fields["Event Date"] = fields.get("Appointment Date", "")
            appointments.append(fields)
    return appointments


def extract_all_cessations_section58(text):
    cessations = []
    blocks = _section58_person_blocks(
        text,
        r"SECTION\s+[A-Z]\s*:\s*CESSATION\s+OF\s+DIRECTOR",
        r"(?:SECTION\s+[A-Z]\s*:|Page\s+\d+\s+of)",
    )
    for block in blocks:
        fields = {}
        for key, pattern in (
            ("IC", r"Identification\s+Number\s+([\d\s-]{10,20})"),
            ("Name", r"Name\s+(.*?)(?:\n|$)"),
            ("Date of Cessation", r"Date\s+of\s+Cessation\s+(\d{2}/\d{2}/\d{4})"),
            ("Cessation Reason", r"Cessation\s+Reason\s+(.*?)(?:\n|$)"),
        ):
            value_match = re.search(pattern, block, re.I)
            if value_match:
                fields[key] = clean(value_match.group(1))
        if fields.get("IC"):
            fields["IC"] = normalize_identifier(fields["IC"])
        if fields.get("Name") or fields.get("IC"):
            fields["Event Type"] = "CEASE"
            fields["Event Date"] = fields.get("Date of Cessation", "")
            cessations.append(fields)
    return cessations


SECTION58_CHANGED_FIELD_PATTERNS = (
    (r"Passport\s+(?:No\.?\s+)?Expiry\s+Date", "Passport Expiry"),
    (r"Identification\s+(?:Number|No\.?)", "IC"),
    (r"Identification\s+Type", "ID Type"),
    (r"Nationality\s+Country", "Nationality"),
    (r"Date\s+of\s+Appointment", "Appointment Date"),
    (r"Date\s+of\s+Birth", "DOB"),
    (r"Business\s+Occupation", "Business Occupation"),
    (r"Residential\s+Address", "Residential"),
    (r"Service\s+Address", "Service Address"),
    (r"Mobile\s+Phone\s+No\.?,?", "Contact No"),
    (r"Phone\s+Number", "Contact No"),
    (r"Contact\s+No\.?,?", "Contact No"),
    (r"Email\s+Address", "Email"),
    (r"Email", "Email"),
    (r"Citizenship", "Citizenship"),
    (r"Nationality", "Nationality"),
    (r"Designation", "Designation"),
    (r"Gender", "Gender"),
    (r"Race", "Race"),
    (r"Name", "Name"),
)


def _legacy_director_change_block(text):
    match = re.search(
        r"SECTION\s+[A-Z]\s*:\s*(?:CHANGE|UPDATE)\s+"
        r"(?:IN\s+)?(?:THE\s+)?PARTICULARS?\s+OF\s+DIRECTOR\b"
        r"(.*?)(?=SECTION\s+[A-Z]\s*:|PARTICULARS\s+OF\s+LODGER|"
        r"I\s+declare\s+that|$)",
        text,
        re.I | re.S,
    )
    return match.group(1) if match else ""


def _legacy_director_change_people(text):
    block = _legacy_director_change_block(text)
    if not block:
        return []
    people = [
        value
        for value in re.split(
            r"(?=Identification\s+(?:Number|No\.?)\s+)",
            block,
            flags=re.I,
        )
        if re.search(r"Identification\s+(?:Number|No\.?)", value, re.I)
    ]
    return people or [block]


def _changed_field_key(label):
    for pattern, key in SECTION58_CHANGED_FIELD_PATTERNS:
        if re.fullmatch(pattern, clean(label), re.I):
            return key
    return ""


def extract_director_updates_section58(text, diagnostics=None):
    """Extract dated field-level director changes from legacy Section 58."""
    updates = []
    diagnostics = diagnostics if diagnostics is not None else []
    label_pattern = "|".join(
        f"(?:{pattern})" for pattern, _ in SECTION58_CHANGED_FIELD_PATTERNS
    )
    row_pattern = re.compile(
        rf"(?P<label>{label_pattern})\s+(?P<value>.*?)\s+"
        r"Date\s+of\s+Change\s*:?\s*"
        r"(?P<date>NIL|\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})",
        re.I | re.S,
    )
    date_pattern = re.compile(
        r"Date\s+of\s+Change\s*:?\s*"
        r"(?P<date>NIL|\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})",
        re.I,
    )
    for person_block in _legacy_director_change_people(text):
        rows = list(row_pattern.finditer(person_block))
        identity = {"Name": "", "IC": ""}
        covered_dates = []
        for row in rows:
            key = _changed_field_key(row.group("label"))
            value = clean(row.group("value")).strip(" :")
            if key == "IC":
                value = normalize_identifier(value)
            if key in identity and value:
                identity[key] = value
        for row in rows:
            key = _changed_field_key(row.group("label"))
            value = clean(row.group("value")).strip(" :")
            if key == "IC":
                value = normalize_identifier(value)
            date_value = row.group("date")
            if date_value.upper() == "NIL":
                continue
            event_date = parse_date(date_value)
            if not event_date:
                continue
            covered_dates.append(row.span("date"))
            normalized_date = event_date.strftime("%d/%m/%Y")
            update = next(
                (
                    item
                    for item in updates
                    if item.get("Event Date") == normalized_date
                    and item.get("Name") == identity.get("Name")
                    and item.get("IC") == identity.get("IC")
                ),
                None,
            )
            if update is None:
                update = {
                    "Event Type": "UPDATE",
                    "Name": identity.get("Name", ""),
                    "IC": identity.get("IC", ""),
                    "Event Date": normalized_date,
                    "Changed Fields": [],
                }
                updates.append(update)
            update[key] = value
            if key not in update["Changed Fields"]:
                update["Changed Fields"].append(key)

        for date_match in date_pattern.finditer(person_block):
            if date_match.group("date").upper() == "NIL":
                continue
            if any(
                start <= date_match.start("date") <= end
                for start, end in covered_dates
            ):
                continue
            diagnostics.append({
                "Code": "UNSUPPORTED_DIRECTOR_UPDATE_FIELD",
                "Date": date_match.group("date"),
                "Raw": clean(
                    person_block[
                        max(0, date_match.start() - 240):date_match.end()
                    ]
                ),
            })
    return updates


def _modern_section58_value(block, label, end_labels):
    end_pattern = "|".join(end_labels)
    match = re.search(
        rf"{label}\s+(.*?)(?=\n\s*(?:{end_pattern})\b|$)",
        block,
        re.I | re.S,
    )
    return clean(match.group(1)).strip(" ,:") if match else ""


def _section58_identifier_value(value):
    mykad = re.search(r"(?<!\d)(\d{12})(?!\d)", str(value or ""))
    if mykad:
        return mykad.group(1)
    token = re.search(r"\b[A-Z][A-Z0-9-]{4,}\b", str(value or ""), re.I)
    return normalize_identifier(token.group(0) if token else value)


def extract_modern_section58_events(text):
    """Extract Section 58(1) ADD DIRECTOR and CEASE DIRECTOR blocks."""
    directors_match = re.search(
        r"\bDIRECTORS\b(.*?)(?=\bLODGER\s+INFORMATION\b|$)",
        text,
        re.I | re.S,
    )
    if not directors_match:
        return []
    block = directors_match.group(1)
    markers = list(re.finditer(
        r"(?:^|\n)\s*(ADD|CEASE)\s+DIRECTOR\s*(?:\n|$)",
        block,
        re.I,
    ))
    events = []
    field_endings = (
        r"Identification\s+Type", r"Identification\s+No\.?",
        r"Nationality\s+Country", r"Citizenship", r"Date\s+of\s+Birth",
        r"Race", r"Gender", r"Residential\s+Address", r"Service\s+Address",
        r"Phone\s+Number", r"Email\s+Address", r"Date\s+of\s+Appointment",
        r"Type\s+of\s+Cessation", r"Date\s+of\s+Cessation",
        r"Upload\s+Resolution", r"Other\s+Information", r"Declaration",
        r"Personal\s+Details", r"Additional\s+Personal\s+Details",
        r"Contact\s+Information", r"Record\s+Details",
        r"Cessation\s+of\s+Director", r"Notes",
    )
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(block)
        person_block = block[start:end]
        operation = marker.group(1).upper()
        name = _modern_section58_value(person_block, r"Name", field_endings)
        identifier = _modern_section58_value(
            person_block, r"Identification\s+No\.?", field_endings
        )
        id_type = _modern_section58_value(
            person_block, r"Identification\s+Type", field_endings
        )
        if operation == "ADD":
            appointment = _modern_section58_value(
                person_block, r"Date\s+of\s+Appointment", field_endings
            )
            event = {
                "Event Type": "APPOINT",
                "Event Date": appointment,
                "Appointment Date": appointment,
                "Name": name,
                "IC": _section58_identifier_value(identifier),
                "ID Type": id_type,
                "Nationality": _modern_section58_value(
                    person_block, r"Nationality\s+Country", field_endings
                ),
                "Citizenship": _modern_section58_value(
                    person_block, r"Citizenship", field_endings
                ),
                "DOB": _modern_section58_value(
                    person_block, r"Date\s+of\s+Birth", field_endings
                ),
                "Race": _modern_section58_value(person_block, r"Race", field_endings),
                "Gender": _modern_section58_value(person_block, r"Gender", field_endings),
                "Residential": _modern_section58_value(
                    person_block, r"Residential\s+Address", field_endings
                ),
                "Service Address": _modern_section58_value(
                    person_block, r"Service\s+Address", field_endings
                ),
                "Contact No": _modern_section58_value(
                    person_block, r"Phone\s+Number", field_endings
                ),
                "Email": _modern_section58_value(
                    person_block, r"Email\s+Address", field_endings
                ),
                "Designation": "DIRECTOR",
            }
        else:
            cessation = _modern_section58_value(
                person_block, r"Date\s+of\s+Cessation", field_endings
            )
            event = {
                "Event Type": "CEASE",
                "Event Date": cessation,
                "Date of Cessation": cessation,
                "Cessation Reason": _modern_section58_value(
                    person_block, r"Type\s+of\s+Cessation", field_endings
                ),
                "Name": name,
                "IC": _section58_identifier_value(identifier),
                "ID Type": id_type,
            }
        if event.get("Name") or event.get("IC"):
            events.append(event)
    return events


def expected_section58_director_events(text):
    """Independently count visible director operations for parse QA."""
    modern = len(re.findall(
        r"(?:^|\n)\s*(?:ADD|CEASE)\s+DIRECTOR\s*(?:\n|$)",
        text,
        re.I,
    ))
    if modern:
        return modern
    expected = 0
    for heading, end_heading in (
        (r"SECTION\s+[A-Z]\s*:\s*NEW\s+DIRECTOR", r"SECTION\s+[A-Z]\s*:"),
        (r"SECTION\s+[A-Z]\s*:\s*CESSATION\s+OF\s+DIRECTOR", r"(?:SECTION\s+[A-Z]\s*:|Page\s+\d+\s+of)"),
    ):
        blocks = _section58_person_blocks(text, heading, end_heading)
        if blocks:
            expected += len(blocks)
    change_people = _legacy_director_change_people(text)
    if change_people:
        for person_block in change_people:
            dates = {
                parse_date(value).strftime("%Y-%m-%d")
                for value in re.findall(
                    r"Date\s+of\s+Change\s*:?\s*"
                    r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})",
                    person_block,
                    re.I,
                )
                if parse_date(value)
            }
            expected += len(dates) or 1
    return expected


@dataclass
class FilingRecord:
    path: str
    folder: str
    size: int
    mtime_ns: int
    sha256: str = ""
    section: str = "OTHER"
    status: str = "VALID"
    quality: int = 2
    confidence: str = "HIGH"
    registration_no: str = ""
    filing_ref: str = ""
    effective_date: datetime | None = None
    lodgement_date: datetime | None = None
    lodgement_date_source: str = ""
    company_name: str = ""
    business_address: str = ""
    financial_address: str = ""
    total_shares: int | None = None
    members: list = field(default_factory=list)
    directors: list = field(default_factory=list)
    officer_events: list = field(default_factory=list)
    expected_director_events: int = 0
    director_parse_diagnostics: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    duplicate_of: str = ""

    def to_json(self):
        return json.dumps(asdict(self), default=_json_default, ensure_ascii=False)

    @classmethod
    def from_json(cls, value):
        data = json.loads(value)
        for key in ("effective_date", "lodgement_date"):
            data[key] = parse_iso_date(data.get(key))
        return cls(**data)


def _event_date(event):
    return parse_date(
        event.get("Event Date")
        or event.get("Appointment Date")
        or event.get("Date of Cessation")
        or event.get("Date")
    )


def build_filing_record(
    path,
    folder_name,
    text=None,
    file_hash=None,
    allow_ocr=True,
):
    path = Path(path)
    stat = path.stat()
    record = FilingRecord(
        path=str(path),
        folder=folder_name,
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=file_hash or file_sha256(path),
        quality=source_quality(path),
    )
    inferred = infer_section_from_path(path)
    if EXCLUDED_STATE_SOURCE.search(str(path)):
        record.section = inferred or "OTHER"
        record.status = "EXCLUDED"
        record.confidence = "HIGH"
        record.warnings.append("Non-statutory or non-final source excluded from current state")
        return record
    if text is None:
        text = read_pdf(path)
    if (
        not clean(text)
        and inferred == "S14"
        and OCR_AVAILABLE
        and allow_ocr
    ):
        text = try_ocr_pdf(path)
        if text:
            record.confidence = "MEDIUM"
            record.warnings.append("OCR fallback used")
    if not clean(text):
        record.section = inferred or "OTHER"
        record.status = "UNREADABLE" if inferred else "OTHER"
        record.confidence = "LOW"
        if inferred:
            record.lodgement_date = date_from_filename(path)
            if record.lodgement_date:
                record.lodgement_date_source = "FILENAME"
            record.effective_date = date_from_filename(path)
            record.warnings.append(
                f"Likely {inferred} filing has no readable text under the current PDF mechanism"
            )
        return record
    record.section = classify_statutory_text(text)
    if record.section == "OTHER":
        record.status = "OTHER"
        return record
    record.registration_no = extract_document_registration_number(text)
    record.filing_ref = extract_filing_reference(text)
    (
        record.lodgement_date,
        record.lodgement_date_source,
    ) = extract_lodgement_date(text, path)

    if record.section == "S68":
        record.effective_date = parse_date(annual_return_date(text))
        record.company_name = company_name(text)
        record.business_address = business_address(text)
        record.financial_address = financial_address(text)
        record.total_shares = parse_number(extract_total_shares(text), None)
        legacy_members = list(extract_members(text))
        legacy_directors = list(extract_directors(text))
        layout_directors, layout_members = extract_section68_layout(path)
        layout_member_total = sum(
            parse_number(member.get("Shares")) for member in layout_members
        )
        record.members = (
            layout_members
            if layout_members
            and (
                record.total_shares is None
                or layout_member_total == record.total_shares
            )
            else legacy_members
        )
        record.directors = (
            layout_directors
            if layout_directors and len(layout_directors) >= len(legacy_directors)
            else legacy_directors
        )
        if record.directors is layout_directors:
            member_addresses = {
                normalize_identifier(member.get("ID No", "")): member.get("Address", "")
                for member in layout_members
                if member.get("ID No") and member.get("Address")
            }
            member_names = {
                normalize_identifier(member.get("ID No", "")): member.get("Name", "")
                for member in layout_members
                if member.get("ID No") and member.get("Name")
            }
            normalized_business = normalize_person_name(record.business_address)
            for director in record.directors:
                identifier = normalize_identifier(director.get("IC", ""))
                residential = director.get("Residential", "")
                service = director.get("Service Address", "")
                member_name = member_names.get(identifier, "")
                if len(member_name) >= len(director.get("Name", "")) + 3:
                    director["Name"] = member_name
                member_address = member_addresses.get(identifier, "")
                if member_address:
                    address_similarity = SequenceMatcher(
                        None,
                        normalize_person_name(residential),
                        normalize_person_name(member_address),
                    ).ratio()
                    if (
                        "MALAYSIA" not in residential.upper()
                        or address_similarity >= 0.65
                    ):
                        director["Residential"] = member_address
                if record.business_address:
                    normalized_service = normalize_person_name(service)
                    similarity = SequenceMatcher(
                        None, normalized_service, normalized_business
                    ).ratio()
                    if "MALAYSIA" not in service.upper() or similarity >= 0.82:
                        director["Service Address"] = record.business_address
        for director in record.directors:
            director["Residential"] = _clean_layout_address([
                director.get("Residential", "")
            ])
            director["Service Address"] = _clean_layout_address([
                director.get("Service Address", "")
            ])
    elif record.section == "S51":
        record.members = list(extract_members_section51(text))
        record.total_shares = parse_number(extract_total_shares_s51(text), None)
        ref_date = extract_ref_date(text)
        member_dates = [
            parse_date(member.get("Date", ""))
            for member in record.members
            if parse_date(member.get("Date", ""))
        ]
        record.effective_date = (
            record.lodgement_date
            or (parse_date(ref_date) if ref_date else None)
            or (max(member_dates) if member_dates else None)
        )
    elif record.section == "S58":
        appointments = extract_all_appointments_section58(text)
        if not appointments:
            for director in extract_directors_section58(text):
                event = deepcopy(director)
                event["Event Type"] = "APPOINT"
                event["Event Date"] = director.get("Appointment Date", "")
                appointments.append(event)
        record.officer_events.extend(appointments)
        cessations = extract_all_cessations_section58(text)
        if not cessations:
            cessation = extract_cessation_section58(text)
            if cessation:
                event = deepcopy(cessation)
                event["Event Type"] = "CEASE"
                event["Event Date"] = cessation.get("Date of Cessation", "")
                cessations.append(event)
        record.officer_events.extend(cessations)
        record.officer_events.extend(
            extract_director_updates_section58(
                text,
                record.director_parse_diagnostics,
            )
        )
        record.officer_events.extend(extract_modern_section58_events(text))
        record.expected_director_events = expected_section58_director_events(text)
        officer_role_match = re.search(
            r"(?:NEW|CESSATION\s+OF|CHANGE\s+IN\s+PARTICULARS\s+OF)\s+"
            r"(SECRETARY|MANAGER)\b",
            text,
            re.I,
        )
        if officer_role_match:
            record.officer_events.append({
                "Event Type": "AUDIT_ONLY_OFFICER_FILING",
                "Role": officer_role_match.group(1).upper(),
                "Event Date": iso_date(record.lodgement_date),
                "Name": "",
                "IC": "",
            })
        dates = [
            _event_date(event)
            for event in record.officer_events
            if _event_date(event)
        ]
        record.effective_date = (
            max(dates)
            if dates
            else record.lodgement_date
        )
    elif record.section == "FORM49":
        record.directors = list(extract_directors(text))
        record.effective_date = record.lodgement_date
    elif record.section == "S78":
        record.effective_date = extract_section78_date(text)
        record.total_shares = extract_total_shares_section78(text)
        record.members = extract_allotments_section78(text)
        for member in record.members:
            member["Event Date"] = iso_date(record.effective_date)
            member["Event Type"] = "ALLOTMENT"
    elif record.section == "S14":
        company = extract_company_section14(text)
        record.company_name = company.get("name", "")
        record.registration_no = company.get("reg_no", "") or record.registration_no
        record.business_address = company.get("business_address", "")
        record.financial_address = company.get("registered_address", "")
        record.effective_date = parse_date(extract_incorporation_date(text))
        record.total_shares = parse_number(
            extract_total_shares_section14(text), None
        )
        record.members = list(extract_members_section14(text))
        record.directors = list(extract_directors_section14(text))

    if not record.effective_date:
        record.effective_date = date_from_filename(path)
        if record.effective_date:
            record.confidence = "LOW"
            record.warnings.append("Effective date inferred from filename")
        else:
            record.warnings.append("No reliable statutory effective date")
    return record


def load_document_cache(db_path):
    db_path = Path(db_path)
    if not db_path.exists():
        return {}
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='Statutory_Documents'"
        ).fetchone()
        if not table:
            return {}
        cache = {}
        for row in connection.execute(
            """
            SELECT SourcePath,Size,MTimeNs,ReaderVersion,ParsedJSON
            FROM Statutory_Documents
            """
        ):
            cache[row["SourcePath"]] = dict(row)
        return cache
    finally:
        connection.close()


def _section14_ocr_candidate_key(record):
    path = Path(record.path)
    name = path.stem.lower()
    if re.fullmatch(r"\s*(?:section|sec)\s*14\s*", name):
        kind = 0
    elif "superform 14" in name:
        kind = 1
    else:
        kind = 2
    return kind, record.size, record.path.lower()


def scan_company_filings(folder, cache=None):
    """Re-extract every eligible PDF; persisted parsed-record cache is ignored."""
    records = []
    for path in sorted(folder.rglob("*.pdf"), key=lambda value: str(value).lower()):
        records.append(
            build_filing_record(
                path,
                folder.name,
                allow_ocr=False,
            )
        )

    has_profile = any(
        record.status == "VALID"
        and record.section in {"S14", "S68"}
        and record.effective_date
        for record in records
    )
    if not has_profile and OCR_AVAILABLE:
        candidates = [
            (index, record)
            for index, record in enumerate(records)
            if record.status == "UNREADABLE" and record.section == "S14"
        ]
        if candidates:
            index, candidate = min(
                candidates,
                key=lambda item: _section14_ocr_candidate_key(item[1]),
            )
            print(
                f"  OCR profile candidate: {Path(candidate.path).name}",
                flush=True,
            )
            text = try_ocr_pdf(candidate.path)
            if clean(text):
                records[index] = build_filing_record(
                    candidate.path,
                    folder.name,
                    text=text,
                    file_hash=candidate.sha256,
                    allow_ocr=False,
                )
    return records


def issue(
    folder,
    severity,
    code,
    message,
    source_path="",
    section="",
    effective_date=None,
):
    return {
        "Folder": folder,
        "Severity": severity,
        "Code": code,
        "SourcePath": source_path,
        "Section": section,
        "EffectiveDate": iso_date(effective_date),
        "Message": message,
    }


def filing_sort_key(record, include_precedence=False):
    return (
        record.effective_date or datetime.min,
        SECTION_PRECEDENCE.get(record.section, 0) if include_precedence else 0,
        record.quality,
        record.filing_ref,
        record.path,
    )


def canonicalize_filings(records):
    issues = []
    for record in records:
        if record.status in {"DUPLICATE", "REG_MISMATCH", "INVALID_SNAPSHOT"}:
            record.status = "VALID"
            record.duplicate_of = ""

    valid = [record for record in records if record.status == "VALID"]
    canonical = []
    by_hash = {}
    for record in sorted(valid, key=filing_sort_key, reverse=True):
        if record.sha256 and record.sha256 in by_hash:
            record.status = "DUPLICATE"
            record.duplicate_of = by_hash[record.sha256].path
            continue
        if record.sha256:
            by_hash[record.sha256] = record
        canonical.append(record)

    registration_aliases = {}
    for record in canonical:
        identifiers = registration_identifiers(record.registration_no)
        if len(identifiers) < 2:
            continue
        preferred = next(
            (
                identifier
                for identifier in identifiers
                if re.fullmatch(r"\d{12}", identifier)
            ),
            identifiers[0],
        )
        for identifier in identifiers:
            registration_aliases[identifier] = preferred

    def resolved_registration(record):
        identifiers = registration_identifiers(record.registration_no)
        if not identifiers:
            return ""
        for identifier in identifiers:
            if identifier in registration_aliases:
                return registration_aliases[identifier]
        return identifiers[0]

    by_reference = {}
    for record in sorted(canonical, key=filing_sort_key, reverse=True):
        reference_key = (
            record.section,
            resolved_registration(record),
            record.filing_ref,
        )
        if not record.filing_ref:
            continue
        if reference_key in by_reference:
            winner = by_reference[reference_key]
            record.status = "DUPLICATE"
            record.duplicate_of = winner.path
            if record.sha256 != winner.sha256:
                issues.append(issue(
                    record.folder,
                    "REVIEW",
                    "FILING_REFERENCE_CONFLICT",
                    (
                        f"Two different files use filing reference {record.filing_ref}; "
                        f"{winner.path} was selected by source quality and chronology."
                    ),
                    record.path,
                    record.section,
                    record.effective_date,
                ))
        else:
            by_reference[reference_key] = record

    canonical = [record for record in canonical if record.status == "VALID"]
    identity_candidates = [
        record
        for record in canonical
        if record.registration_no and record.section in {"S14", "S68", "S51", "S58", "S78"}
    ]
    profile_candidates = [
        record
        for record in identity_candidates
        if record.section in {"S14", "S68"}
    ]
    identity_pool = profile_candidates or identity_candidates
    registration_counts = {}
    for record in identity_pool:
        normalized = resolved_registration(record)
        if normalized:
            registration_counts[normalized] = (
                registration_counts.get(normalized, 0) + 1
            )
    established_registration = ""
    if registration_counts:
        highest_count = max(registration_counts.values())
        tied_numbers = {
            number
            for number, count in registration_counts.items()
            if count == highest_count
        }
        latest_tied_source = max(
            (
                record
                for record in identity_pool
                if resolved_registration(record)
                in tied_numbers
            ),
            key=lambda record: filing_sort_key(record, True),
            default=None,
        )
        established_registration = (
            resolved_registration(latest_tied_source)
            if latest_tied_source
            else ""
        )
    identity_source = max(
        (
            record
            for record in identity_pool
            if resolved_registration(record)
            == established_registration
        ),
        key=lambda record: filing_sort_key(record, True),
        default=None,
    )
    if established_registration:
        for record in canonical:
            current = resolved_registration(record)
            if current and current != established_registration:
                record.status = "REG_MISMATCH"
                issues.append(issue(
                    record.folder,
                    "CRITICAL",
                    "REGISTRATION_NUMBER_MISMATCH",
                    (
                        f"Document registration number {record.registration_no} does not "
                        f"match established number {identity_source.registration_no}."
                    ),
                    record.path,
                    record.section,
                    record.effective_date,
                ))
    canonical = [record for record in canonical if record.status == "VALID"]
    canonical.sort(key=filing_sort_key)
    return canonical, issues


def normalize_member(raw, section):
    if section == "S51":
        member = {
            "Type": raw.get("Type", "INDIVIDUAL"),
            "Name": raw.get("Name", ""),
            "ID Type": (
                "MYKAD"
                if re.fullmatch(r"\d{12}", normalize_identifier(raw.get("IC", "")))
                else ""
            ),
            "ID No": normalize_identifier(raw.get("IC", "")),
            "Nationality": raw.get("Nationality", ""),
            "Race": raw.get("Race", ""),
            "Gender": raw.get("Gender", ""),
            "DOB": raw.get("DOB", ""),
            "Address": raw.get("Address", ""),
            "Shares": parse_number(raw.get("Shares")),
            "Share Type": raw.get("Share Type", "ORDINARY SHARES"),
            "Analysis": raw.get("Analysis", ""),
            "Transferred In": parse_number(raw.get("Transferred In")),
            "Transferred Out": parse_number(raw.get("Transferred Out")),
            "Final Shares": parse_number(raw.get("Shares")),
            "Member Date": raw.get("Date", ""),
        }
    else:
        member = {
            "Type": raw.get("Type", ""),
            "Name": raw.get("Name", ""),
            "ID Type": raw.get("ID Type", ""),
            "ID No": normalize_identifier(raw.get("ID No", "") or raw.get("IC", "")),
            "Nationality": raw.get("Nationality", ""),
            "Race": raw.get("Race", ""),
            "Gender": raw.get("Gender", ""),
            "DOB": raw.get("DOB", ""),
            "Address": raw.get("Address", ""),
            "Shares": parse_number(raw.get("Shares")),
            "Share Type": raw.get("Share Type", ""),
            "Analysis": raw.get("Analysis", ""),
        }
        if "Allotted Shares" in raw:
            member["Allotted Shares"] = parse_number(raw.get("Allotted Shares"))
            member["Event Date"] = raw.get("Event Date", "")
            member["Event Type"] = raw.get("Event Type", "ALLOTMENT")
    if not member["Type"] or not member["ID Type"]:
        member_type, id_type = _member_identity_fields(
            member["ID No"], member["Name"]
        )
        member["Type"] = member["Type"] or member_type
        member["ID Type"] = member["ID Type"] or id_type
    return member


def normalize_director_date(value):
    parsed = parse_date(value)
    return iso_date(parsed) if parsed else clean(value)


def normalize_director(raw):
    return {
        "Name": raw.get("Name", ""),
        "IC": normalize_identifier(
            raw.get("IC", "")
            or raw.get("ID No", "")
            or raw.get("Identification Number", "")
        ),
        "ID Type": raw.get(
            "ID Type", raw.get("Identification Type", "")
        ),
        "DOB": normalize_director_date(
            raw.get("DOB", raw.get("Date of Birth", ""))
        ),
        "Passport Expiry": normalize_director_date(
            raw.get("Passport Expiry", "")
        ),
        "Nationality": raw.get("Nationality", ""),
        "Citizenship": raw.get("Citizenship", ""),
        "Race": raw.get("Race", ""),
        "Gender": raw.get("Gender", ""),
        "Designation": raw.get("Designation", ""),
        "Business Occupation": raw.get("Business Occupation", ""),
        "Residential": raw.get(
            "Residential", raw.get("Residential Address", "")
        ),
        "Service Address": raw.get("Service Address", ""),
        "Email": raw.get("Email", raw.get("Email Address", "")),
        "Contact No": raw.get(
            "Contact No",
            raw.get("Phone Number", raw.get("Mobile Phone No", "")),
        ),
        "Appointment Date": normalize_director_date(
            raw.get("Appointment Date", "")
        ),
    }


def member_analysis(member):
    if member.get("Analysis"):
        return member["Analysis"]
    nationality = str(member.get("Nationality", "")).upper()
    race = str(member.get("Race", "")).upper()
    if nationality and nationality not in {"MALAYSIA", "MALAYSIAN"}:
        return "NON-CITIZENS"
    if race in {"MALAY", "BUMIPUTERA", "NATIVE"}:
        return "CITIZENS WHO ARE MALAYS AND NATIVES"
    if nationality in {"MALAYSIA", "MALAYSIAN"} and race:
        return "CITIZENS WHO ARE NON - MALAYS AND NON- NATIVES"
    return ""


def aggregate_member_rows(members):
    """Combine one person's separate share-class rows without double counting."""
    aggregated = {}
    order = []
    seen_rows = set()
    for member in members:
        key = person_key(member)
        if not key:
            continue
        shares = parse_number(member.get("Shares"))
        share_type = clean(member.get("Share Type", "")).upper()
        row_signature = (key, shares, share_type)
        if row_signature in seen_rows:
            continue
        seen_rows.add(row_signature)
        if key not in aggregated:
            current = deepcopy(member)
            current["Shares"] = shares
            aggregated[key] = current
            order.append(key)
            continue
        current = aggregated[key]
        current_shares = parse_number(current.get("Shares"))
        # Keep the first row's identity/address details; later rows commonly
        # represent an additional share class for the same person.
        merged = merge_nonempty(member, current)
        merged["Shares"] = current_shares + shares
        for field_name in ("Share Type", "Analysis"):
            values = []
            for value in (current.get(field_name, ""), member.get(field_name, "")):
                value = clean(value)
                if value and value not in values:
                    values.append(value)
            merged[field_name] = " | ".join(values)
        aggregated[key] = merged
    return [aggregated[key] for key in order]


def build_person_registry(records):
    registry = {}
    for record in sorted(records, key=filing_sort_key):
        for raw in record.members:
            member = normalize_member(raw, record.section)
            key = person_key(member)
            if key:
                registry[key] = merge_nonempty(registry.get(key, {}), member)
        for raw in record.directors:
            director = normalize_director(raw)
            key = person_key(director)
            if key:
                registry[key] = merge_nonempty(registry.get(key, {}), director)
        for raw in record.officer_events:
            if raw.get("Event Type") == "AUDIT_ONLY_OFFICER_FILING":
                continue
            director = normalize_director(raw)
            key = person_key(director)
            if key:
                registry[key] = merge_nonempty(registry.get(key, {}), director)
    return registry


def enrich_person(person, registry):
    key = person_key(person)
    enriched = merge_nonempty(registry.get(key, {}), person)
    if "Shares" in enriched:
        enriched["Analysis"] = member_analysis(enriched)
    return enriched


def validate_member_snapshot(record, registry):
    members = aggregate_member_rows([
        enrich_person(normalize_member(raw, record.section), registry)
        for raw in record.members
    ])
    active = [member for member in members if parse_number(member.get("Shares")) > 0]
    errors = []
    if record.total_shares is not None and record.total_shares < 0:
        errors.append("issued-share total is negative")
    if any(parse_number(member.get("Shares")) < 0 for member in members):
        errors.append("a member balance is negative")
    if record.total_shares and not active:
        errors.append("issued shares are present but no active members were extracted")
    if active and record.total_shares is not None:
        member_total = sum(parse_number(member.get("Shares")) for member in active)
        if member_total != record.total_shares:
            errors.append(
                f"active member shares total {member_total:,}, expected {record.total_shares:,}"
            )
    return active, errors


def member_snapshot_signature(record, members):
    return (
        record.total_shares,
        tuple(sorted(
            (
                person_key(member),
                parse_number(member.get("Shares")),
            )
            for member in members
        )),
    )


def _match_existing_person(state, person, issues, folder, record, role):
    key = person_key(person)
    if key in state:
        return key
    name = normalize_person_name(person.get("Name"))
    if not name:
        return key
    matches = [
        existing_key
        for existing_key, existing in state.items()
        if normalize_person_name(existing.get("Name")) == name
    ]
    if len(matches) == 1:
        issues.append(issue(
            folder,
            "REVIEW",
            f"{role.upper()}_NAME_FALLBACK",
            (
                f"{person.get('Name', '')} was matched by unique normalized name "
                "because the identification number did not match."
            ),
            record.path,
            record.section,
            record.effective_date,
        ))
        return matches[0]
    return key


def resolve_members(folder, records, registry, issues):
    snapshot_candidates = [
        record
        for record in records
        if record.section in {"S14", "S68", "S51"}
        and record.members
        and record.effective_date
    ]
    valid_snapshots = []
    snapshot_members = {}
    for record in snapshot_candidates:
        active, errors = validate_member_snapshot(record, registry)
        if errors:
            record.status = "INVALID_SNAPSHOT"
            issues.append(issue(
                folder,
                "CRITICAL",
                "INVALID_MEMBER_SNAPSHOT",
                (
                    "Member snapshot was not promoted: "
                    + "; ".join(errors)
                    + ". The last validated snapshot remains in use."
                ),
                record.path,
                record.section,
                record.effective_date,
            ))
            continue
        valid_snapshots.append(record)
        snapshot_members[record.path] = active
    conflicting_paths = set()
    snapshots_by_date_section = {}
    for record in valid_snapshots:
        group_key = (record.effective_date, record.section)
        snapshots_by_date_section.setdefault(group_key, []).append(record)
    for (effective_date, section), group in snapshots_by_date_section.items():
        signatures = {
            member_snapshot_signature(
                record,
                snapshot_members[record.path],
            )
            for record in group
        }
        if len(signatures) > 1:
            conflicting_paths.update(record.path for record in group)
            issues.append(issue(
                folder,
                "CRITICAL",
                "SAME_DATE_MEMBER_SNAPSHOT_CONFLICT",
                (
                    f"Conflicting {section} member snapshots share the same "
                    "effective date; the last earlier validated snapshot remains in use."
                ),
                group[0].path,
                section,
                effective_date,
            ))
    valid_snapshots = [
        record
        for record in valid_snapshots
        if record.path not in conflicting_paths
    ]
    snapshot = max(
        valid_snapshots,
        key=lambda record: filing_sort_key(record, True),
        default=None,
    )
    members = {}
    if snapshot:
        for member in snapshot_members[snapshot.path]:
            key = person_key(member)
            if key:
                member["_SourcePath"] = snapshot.path
                members[key] = member
    total_shares = snapshot.total_shares if snapshot else None
    snapshot_date = snapshot.effective_date if snapshot else None

    allotment_records = sorted(
        (
            record
            for record in records
            if record.section == "S78" and record.effective_date
            and (snapshot_date is None or record.effective_date > snapshot_date)
        ),
        key=filing_sort_key,
    )
    for record in allotment_records:
        if not record.members:
            issues.append(issue(
                folder,
                "CRITICAL",
                "UNPARSED_ALLOTMENT",
                "Section 78 was identified but no allottee rows could be extracted.",
                record.path,
                record.section,
                record.effective_date,
            ))
            continue
        for raw in record.members:
            allottee = enrich_person(normalize_member(raw, "S78"), registry)
            key = _match_existing_person(
                members, allottee, issues, folder, record, "member"
            )
            if not key:
                issues.append(issue(
                    folder,
                    "CRITICAL",
                    "ALLOTTEE_IDENTITY_MISSING",
                    "An allottee could not be identified and was not applied.",
                    record.path,
                    record.section,
                    record.effective_date,
                ))
                continue
            prior = members.get(key, {})
            merged = merge_nonempty(prior, allottee)
            allotted = parse_number(
                allottee.get("Allotted Shares", allottee.get("Shares"))
            )
            merged["Shares"] = parse_number(prior.get("Shares")) + allotted
            merged["Event Type"] = "ALLOTMENT"
            merged["Event Date"] = iso_date(record.effective_date)
            merged["_SourcePath"] = record.path
            members[key] = merged
        if record.total_shares is not None:
            total_shares = record.total_shares
        elif total_shares is not None:
            total_shares += sum(
                parse_number(member.get("Allotted Shares", member.get("Shares")))
                for member in (
                    normalize_member(raw, "S78") for raw in record.members
                )
            )

    current = [
        member for member in members.values()
        if parse_number(member.get("Shares")) > 0
    ]
    current.sort(
        key=lambda member: (
            -parse_number(member.get("Shares")),
            clean(member.get("Name", "")),
        )
    )
    if total_shares is not None and current:
        current_total = sum(parse_number(member.get("Shares")) for member in current)
        if current_total != total_shares:
            issues.append(issue(
                folder,
                "CRITICAL",
                "SHARE_RECONCILIATION",
                (
                    f"Resolved active member shares total {current_total:,}, "
                    f"but issued shares are {total_shares:,}."
                ),
                (
                    allotment_records[-1].path
                    if allotment_records
                    else snapshot.path if snapshot else ""
                ),
                (
                    allotment_records[-1].section
                    if allotment_records
                    else snapshot.section if snapshot else ""
                ),
                (
                    allotment_records[-1].effective_date
                    if allotment_records
                    else snapshot.effective_date if snapshot else None
                ),
            ))
    for member in current:
        member.pop("_SourcePath", None)
    return current, total_shares, snapshot


def resolve_total_shares(records, member_total=None):
    """Resolve statutory issued shares independently of member extraction."""
    explicit = [
        record
        for record in records
        if record.section in {"S14", "S51", "S68", "S78"}
        and record.effective_date
        and record.total_shares is not None
    ]
    latest_explicit = max(explicit, key=filing_sort_key, default=None)
    latest_allotment = max(
        (
            record
            for record in records
            if record.section == "S78" and record.effective_date
        ),
        key=filing_sort_key,
        default=None,
    )
    if (
        latest_allotment
        and latest_explicit
        and latest_allotment.effective_date > latest_explicit.effective_date
        and member_total is not None
    ):
        return member_total
    if latest_explicit:
        return latest_explicit.total_shares
    return member_total


def resolve_directors(folder, records, registry, issues):
    snapshots = [
        record
        for record in records
        if record.section in {"S14", "S68", "FORM49"}
        and record.directors
        and record.effective_date
    ]
    snapshot = max(
        snapshots,
        key=lambda record: filing_sort_key(record, True),
        default=None,
    )
    directors = {}
    if snapshot:
        for raw in snapshot.directors:
            director = enrich_person(normalize_director(raw), registry)
            key = person_key(director)
            if key:
                directors[key] = director

    baseline_date = snapshot.effective_date if snapshot else None
    dated_events = []
    for record in records:
        if record.section != "S58":
            continue
        for event in record.officer_events:
            event_type = event.get("Event Type", "")
            if event_type == "AUDIT_ONLY_OFFICER_FILING":
                continue
            event_date = _event_date(event)
            if not event_date:
                issues.append(issue(
                    folder,
                    "CRITICAL",
                    "UNDATED_DIRECTOR_EVENT",
                    "A Section 58 director event has no reliable effective date and was not applied.",
                    record.path,
                    record.section,
                    record.effective_date,
                ))
                continue
            if baseline_date and event_date < baseline_date:
                continue
            dated_events.append((event_date, record, event))

    conflicts = set()
    grouped = {}
    for event_date, record, event in dated_events:
        subject = person_key(normalize_director(event))
        group_key = (event_date, subject)
        grouped.setdefault(group_key, []).append((record, event))
    for (event_date, subject), group in grouped.items():
        types = {event.get("Event Type") for _, event in group}
        if len(types) > 1 and subject:
            conflicts.add((event_date, subject))
            record = group[0][0]
            issues.append(issue(
                folder,
                "CRITICAL",
                "SAME_DATE_DIRECTOR_CONFLICT",
                (
                    "Conflicting director events share the same effective date; "
                    "the last non-conflicting state was retained."
                ),
                record.path,
                record.section,
                event_date,
            ))

    for event_date, record, event in sorted(
        dated_events,
        key=lambda item: (
            item[0], item[1].quality, item[1].filing_ref, item[1].path
        ),
    ):
        director = enrich_person(normalize_director(event), registry)
        subject = person_key(director)
        if (event_date, subject) in conflicts:
            continue
        key = _match_existing_person(
            directors, director, issues, folder, record, "director"
        )
        if not key:
            issues.append(issue(
                folder,
                "CRITICAL",
                "DIRECTOR_IDENTITY_MISSING",
                "A Section 58 director event could not be identified and was not applied.",
                record.path,
                record.section,
                event_date,
            ))
            continue
        event_type = event.get("Event Type")
        if event_type == "CEASE":
            directors.pop(key, None)
        elif event_type in {"APPOINT", "UPDATE"}:
            merged = merge_nonempty(directors.get(key, {}), director)
            if event_type == "UPDATE":
                updated_key = person_key(merged)
                if updated_key and updated_key != key:
                    collision = directors.get(updated_key)
                    if collision and normalize_person_name(
                        collision.get("Name")
                    ) != normalize_person_name(merged.get("Name")):
                        issues.append(issue(
                            folder,
                            "CRITICAL",
                            "DIRECTOR_IDENTITY_REKEY_CONFLICT",
                            (
                                "A director identification change conflicts with "
                                "another current director and was not re-keyed."
                            ),
                            record.path,
                            record.section,
                            event_date,
                        ))
                    else:
                        directors.pop(key, None)
                        key = updated_key
            directors[key] = merged

    current = list(directors.values())
    current.sort(
        key=lambda director: (
            parse_date(director.get("Appointment Date", "")) or datetime.min,
            clean(director.get("Name", "")),
        )
    )
    return current, snapshot


def record_events(record):
    rows = []
    if record.section in {"S14", "S68", "S51"}:
        for raw in record.members:
            member = normalize_member(raw, record.section)
            rows.append({
                "Folder": record.folder,
                "SourcePath": record.path,
                "Section": record.section,
                "EventType": (
                    "MEMBER_REGISTER_SNAPSHOT"
                    if record.section == "S51"
                    else "MEMBER_SNAPSHOT"
                ),
                "EffectiveDate": (
                    iso_date(parse_date(member.get("Member Date", "")))
                    or iso_date(record.effective_date)
                ),
                "SubjectKey": person_key(member),
                "SubjectName": member.get("Name", ""),
                "PayloadJSON": json.dumps(
                    member, ensure_ascii=False, default=_json_default
                ),
            })
    if record.section == "S78":
        for raw in record.members:
            member = normalize_member(raw, "S78")
            rows.append({
                "Folder": record.folder,
                "SourcePath": record.path,
                "Section": record.section,
                "EventType": "ALLOTMENT",
                "EffectiveDate": iso_date(record.effective_date),
                "SubjectKey": person_key(member),
                "SubjectName": member.get("Name", ""),
                "PayloadJSON": json.dumps(member, ensure_ascii=False),
            })
    if record.section == "S58":
        for event in record.officer_events:
            director = normalize_director(event)
            rows.append({
                "Folder": record.folder,
                "SourcePath": record.path,
                "Section": record.section,
                "EventType": event.get("Event Type", "OFFICER_FILING"),
                "EffectiveDate": (
                    iso_date(_event_date(event))
                    or iso_date(record.effective_date)
                ),
                "SubjectKey": person_key(director),
                "SubjectName": director.get("Name", ""),
                "PayloadJSON": json.dumps(event, ensure_ascii=False),
            })
    return rows


def latest_section_lodgement(records, section):
    """Return the latest valid lodgement date recorded for one section."""
    candidates = [
        record
        for record in records
        if (
            record.status == "VALID"
            and record.section == section
            and record.lodgement_date
        )
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda record: (
            record.lodgement_date,
            filing_sort_key(record, True),
        ),
    ).lodgement_date


def resolve_company_event_aware(folder, records, canonical_issues=None):
    issues = list(canonical_issues or [])
    canonical = [record for record in records if record.status == "VALID"]
    if not canonical:
        return None, [], issues
    registry = build_person_registry(canonical)
    annual_returns = [
        record for record in canonical
        if record.section == "S68" and record.effective_date
    ]
    annual_return = max(
        annual_returns, key=filing_sort_key, default=None
    )
    incorporation_records = [
        record for record in canonical
        if record.section == "S14" and record.effective_date
    ]
    incorporation = max(
        incorporation_records, key=filing_sort_key, default=None
    )
    profile = annual_return or max(
        incorporation_records, key=filing_sort_key, default=None
    )
    if not profile:
        issues.append(issue(
            folder.name,
            "CRITICAL",
            "NO_PROFILE_SNAPSHOT",
            "No readable Section 68 or Section 14 profile snapshot was found.",
        ))
        return None, [], issues

    members, member_total, member_snapshot = resolve_members(
        folder.name, canonical, registry, issues
    )
    total_shares = resolve_total_shares(canonical, member_total)
    directors, director_snapshot = resolve_directors(
        folder.name, canonical, registry, issues
    )

    latest_name_record = max(
        (record for record in canonical if record.company_name),
        key=filing_sort_key,
        default=profile,
    )
    current_name = latest_name_record.company_name or folder.name
    changed_name = find_section27_new_name(folder)
    if changed_name:
        current_name = changed_name

    section51_lodgement = latest_section_lodgement(canonical, "S51")
    section58_lodgement = latest_section_lodgement(canonical, "S58")
    section78_lodgement = latest_section_lodgement(canonical, "S78")

    row = {
        "Folder": folder.name,
        "Company Name": current_name,
        "Reg No": profile.registration_no,
        "Annual Return Date": (
            annual_return.effective_date.strftime("%d/%m/%Y")
            if annual_return
            else ""
        ),
        "Date of Lodgement (AR)": (
            annual_return.lodgement_date.strftime("%d/%m/%Y")
            if annual_return and annual_return.lodgement_date
            else ""
        ),
        "Section 51 Date": (
            section51_lodgement.strftime("%d/%m/%Y")
            if section51_lodgement
            else ""
        ),
        "Section 58 Date": (
            section58_lodgement.strftime("%d/%m/%Y")
            if section58_lodgement
            else ""
        ),
        "Section 78 Date": (
            section78_lodgement.strftime("%d/%m/%Y")
            if section78_lodgement
            else ""
        ),
        "Incorporate Date": (
            incorporation.effective_date.strftime("%d/%m/%Y")
            if incorporation
            else ""
        ),
        "Total Issued Shares": (
            total_shares if total_shares is not None else ""
        ),
        "Business Address": profile.business_address,
        "Financial Record Address": profile.financial_address,
    }
    if not row["Incorporate Date"]:
        row["Incorporate Date"] = find_incorporation_date_in_folder(folder)

    for index, director in enumerate(directors, start=1):
        for column_name, field_name in DIRECTOR_OUTPUT_FIELDS:
            row[f"Director{index} {column_name}"] = director.get(
                field_name, ""
            )
    row["_members"] = members

    for record in records:
        if record.status == "VALID" and record.section == "S58":
            parsed_director_events = sum(
                event.get("Event Type")
                in {"APPOINT", "CEASE", "UPDATE"}
                for event in record.officer_events
            )
            if (
                record.expected_director_events
                and not parsed_director_events
            ):
                issues.append(issue(
                    folder.name,
                    "CRITICAL",
                    "UNPARSED_DIRECTOR_FILING",
                    (
                        "A Section 58 director filing contains "
                        f"{record.expected_director_events} visible operation(s), "
                        "but none were parsed; the earlier director state was retained."
                    ),
                    record.path,
                    record.section,
                    record.effective_date,
                ))
            elif parsed_director_events < record.expected_director_events:
                issues.append(issue(
                    folder.name,
                    "CRITICAL",
                    "PARTIAL_DIRECTOR_EVENT_PARSE",
                    (
                        "A Section 58 director filing contains "
                        f"{record.expected_director_events} visible operation(s), but "
                        f"only {parsed_director_events} were parsed."
                    ),
                    record.path,
                    record.section,
                    record.effective_date,
                ))
            for diagnostic in record.director_parse_diagnostics:
                issues.append(issue(
                    folder.name,
                    "CRITICAL",
                    diagnostic.get(
                        "Code", "UNSUPPORTED_DIRECTOR_UPDATE_FIELD"
                    ),
                    (
                        "A dated director field could not be mapped: "
                        f"{diagnostic.get('Raw', '')}"
                    ),
                    record.path,
                    record.section,
                    parse_date(diagnostic.get("Date"))
                    or record.effective_date,
                ))
        if record.status == "UNREADABLE" and record.section in SUPPORTED_SECTIONS:
            issues.append(issue(
                folder.name,
                "CRITICAL",
                "POTENTIALLY_STALE_UNREADABLE_FILING",
                (
                    "The last validated state was retained because this likely "
                    f"{record.section} filing is unreadable."
                ),
                record.path,
                record.section,
                record.effective_date,
            ))
        for warning in record.warnings:
            if record.status in {"VALID", "UNREADABLE"}:
                issues.append(issue(
                    folder.name,
                    "REVIEW",
                    "DOCUMENT_WARNING",
                    warning,
                    record.path,
                    record.section,
                    record.effective_date,
                ))

    events = []
    for record in canonical:
        events.extend(record_events(record))
    return row, events, issues


def save_to_sqlite(df, table_name, db_dir=DB_DIR, audit_tables=None):
    """Atomically replace the master and statutory audit tables."""
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "csai_master.db"
    temp_path = db_dir / ".csai_master.tmp.db"

    if temp_path.exists():
        temp_path.unlink()
    if db_path.exists():
        shutil.copy2(db_path, temp_path)

    connection = sqlite3.connect(temp_path)
    try:
        with connection:
            df.to_sql(table_name, connection, if_exists="replace", index=False)
            for audit_name, audit_df in (audit_tables or {}).items():
                audit_df.to_sql(
                    audit_name,
                    connection,
                    if_exists="replace",
                    index=False,
                )
            if audit_tables and "Statutory_Documents" in audit_tables:
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS "
                    "idx_statutory_documents_folder_section "
                    "ON Statutory_Documents(Folder, Section)"
                )
            if audit_tables and "Statutory_Events" in audit_tables:
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS "
                    "idx_statutory_events_folder_date "
                    "ON Statutory_Events(Folder, EffectiveDate)"
                )
    finally:
        connection.close()
    os.replace(temp_path, db_path)
    return db_path


def save_outputs(df, audit_tables=None):
    """Write Excel and SQLite outputs after extraction has completed."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_excel = OUTPUT_FILE.with_name(f".{OUTPUT_FILE.stem}.tmp.xlsx")
    if temp_excel.exists():
        temp_excel.unlink()
    df.to_excel(temp_excel, index=False)
    db_path = save_to_sqlite(
        df,
        "Client_Master",
        audit_tables=audit_tables,
    )
    os.replace(temp_excel, OUTPUT_FILE)
    return OUTPUT_FILE, db_path


def arrange_director_columns(rows):
    """Keep every Director 1..N field contiguous before member columns.

    DataFrame builds its column order from the first dictionaries it sees. If
    an early company has only three directors, a Director4 field first seen in
    a later company would otherwise be appended after the member columns.
    """
    director_fields = [
        column_name for column_name, _ in DIRECTOR_OUTPUT_FIELDS
    ]
    max_directors = max(
        (
            int(match.group(1))
            for row in rows
            for key in row
            for match in [re.fullmatch(r"Director(\d+) Name", key)]
            if match
        ),
        default=0,
    )
    director_prefix = re.compile(r"^Director\d+ ")
    for row in rows:
        director_values = {
            key: value
            for key, value in row.items()
            if director_prefix.match(key)
        }
        base_items = [
            (key, value)
            for key, value in row.items()
            if not director_prefix.match(key)
        ]
        arranged = {}
        inserted = False
        for key, value in base_items:
            if key == "_members" and not inserted:
                for index in range(1, max_directors + 1):
                    for field in director_fields:
                        column = f"Director{index} {field}"
                        arranged[column] = director_values.get(column, "")
                inserted = True
            arranged[key] = value
        if not inserted:
            for index in range(1, max_directors + 1):
                for field in director_fields:
                    column = f"Director{index} {field}"
                    arranged[column] = director_values.get(column, "")
        row.clear()
        row.update(arranged)
    return rows


def flatten_member_columns(rows):
    arrange_director_columns(rows)
    max_members = max(
        (len(row.get("_members", [])) for row in rows),
        default=0,
    )
    member_fields = [
        ("Type", "Type"),
        ("Name", "Name"),
        ("ID Type", "ID Type"),
        ("ID No", "ID No"),
        ("Nationality", "Nationality"),
        ("Race", "Race"),
        ("Gender", "Gender"),
        ("DOB", "DOB"),
        ("Address", "Address"),
        ("Shares", "Shares"),
        ("Share Type", "Share Type"),
        ("Analysis", "Analysis"),
    ]
    for row in rows:
        members = row.pop("_members", [])
        for index in range(max_members):
            prefix = f"Member{index + 1}"
            member = members[index] if index < len(members) else {}
            for column_key, member_key in member_fields:
                row[f"{prefix} {column_key}"] = member.get(member_key, "")
    return rows


def document_audit_row(record):
    return {
        "Folder": record.folder,
        "SourcePath": record.path,
        "Size": record.size,
        "MTimeNs": record.mtime_ns,
        "SHA256": record.sha256,
        "FilingReference": record.filing_ref,
        "Section": record.section,
        "EffectiveDate": iso_date(record.effective_date),
        "LodgementDate": iso_date(record.lodgement_date),
        "LodgementDateSource": record.lodgement_date_source,
        "RegistrationNo": record.registration_no,
        "Quality": record.quality,
        "Status": record.status,
        "Confidence": record.confidence,
        "DuplicateOf": record.duplicate_of,
        "ReaderVersion": DOCUMENT_READER_VERSION,
        "ParsedJSON": record.to_json(),
    }


def compare_with_existing_master(new_df, output_file=OUTPUT_FILE):
    if not Path(output_file).exists():
        return {
            "existing_rows": 0,
            "new_rows": len(new_df),
            "added": len(new_df),
            "removed": 0,
            "changed": 0,
            "changed_folders": [],
        }
    old_df = pd.read_excel(output_file, dtype=str).fillna("")
    new_values = new_df.astype(str).fillna("")
    old_values = old_df.astype(str).fillna("")
    old_by_folder = {
        row.get("Folder", ""): row
        for row in old_values.to_dict(orient="records")
    }
    new_by_folder = {
        row.get("Folder", ""): row
        for row in new_values.to_dict(orient="records")
    }
    old_folders = set(old_by_folder)
    new_folders = set(new_by_folder)
    common_columns = [
        column
        for column in old_values.columns
        if column in new_values.columns and column != "UpdatedAt"
    ]
    changed = 0
    changed_folders = []
    for folder in old_folders & new_folders:
        if any(
            str(old_by_folder[folder].get(column, ""))
            != str(new_by_folder[folder].get(column, ""))
            for column in common_columns
        ):
            changed += 1
            changed_folders.append(folder)
    return {
        "existing_rows": len(old_df),
        "new_rows": len(new_df),
        "added": len(new_folders - old_folders),
        "removed": len(old_folders - new_folders),
        "changed": changed,
        "changed_folders": sorted(changed_folders, key=str.lower),
    }


def run_event_aware_extraction(
    client_root=CLIENT_ROOT,
    persist=True,
    comparison_mode=False,
):
    client_root = Path(client_root)
    rows = []
    all_records = []
    all_events = []
    all_issues = []

    folders = [
        folder
        for folder in sorted(
            client_root.iterdir(),
            key=lambda value: value.name.lower(),
        )
        if (
            folder.is_dir()
            and (
                not CLIENT_FILTER_PATTERN
                or re.search(CLIENT_FILTER_PATTERN, folder.name, re.I)
            )
        )
    ]

    for company_index, folder in enumerate(folders, start=1):
        started = time.perf_counter()
        print(
            f"Processing [{company_index}/{len(folders)}] : {folder.name}",
            flush=True,
        )
        records = scan_company_filings(folder)
        _, canonical_issues = canonicalize_filings(records)
        row, events, issues = resolve_company_event_aware(
            folder,
            records,
            canonical_issues,
        )
        all_records.extend(records)
        all_events.extend(events)
        all_issues.extend(issues)
        if row:
            rows.append(row)
        excluded = sum(record.status == "EXCLUDED" for record in records)
        unreadable = sum(record.status == "UNREADABLE" for record in records)
        parsed = len(records) - excluded - unreadable
        print(
            "  "
            f"PDFs={len(records)} parsed={parsed} excluded={excluded} "
            f"unreadable={unreadable} elapsed={time.perf_counter() - started:.1f}s",
            flush=True,
        )

    flatten_member_columns(rows)
    df = pd.DataFrame(rows)
    string_columns = [
        column
        for column in df.columns
        if "IC" in column or "ID No" in column
    ]
    for column in string_columns:
        df[column] = df[column].apply(
            lambda value: (
                str(int(value))
                if pd.notna(value)
                and isinstance(value, float)
                and value == int(value)
                else str(value) if pd.notna(value) else ""
            )
        )
    df["UpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    document_columns = [
        "Folder", "SourcePath", "Size", "MTimeNs", "SHA256",
        "FilingReference", "Section", "EffectiveDate", "LodgementDate",
        "LodgementDateSource", "RegistrationNo", "Quality", "Status",
        "Confidence", "DuplicateOf", "ReaderVersion", "ParsedJSON",
    ]
    event_columns = [
        "Folder", "SourcePath", "Section", "EventType", "EffectiveDate",
        "SubjectKey", "SubjectName", "PayloadJSON",
    ]
    issue_columns = [
        "Folder", "Severity", "Code", "SourcePath", "Section",
        "EffectiveDate", "Message",
    ]
    audit_tables = {
        "Statutory_Documents": pd.DataFrame(
            [document_audit_row(record) for record in all_records],
            columns=document_columns,
        ),
        "Statutory_Events": pd.DataFrame(
            all_events,
            columns=event_columns,
        ),
        "Extraction_Issues": pd.DataFrame(
            all_issues,
            columns=issue_columns,
        ),
    }
    comparison = compare_with_existing_master(df)
    issue_code_counts = {}
    for item in all_issues:
        issue_code_counts[item["Code"]] = (
            issue_code_counts.get(item["Code"], 0) + 1
        )
    comparison.update({
        "documents": len(all_records),
        "events": len(all_events),
        "critical_issues": sum(
            item["Severity"] == "CRITICAL" for item in all_issues
        ),
        "review_issues": sum(
            item["Severity"] == "REVIEW" for item in all_issues
        ),
        "issue_codes": dict(sorted(
            issue_code_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )),
    })
    if comparison_mode:
        print("COMPARISON :", json.dumps(comparison, sort_keys=True))
    if persist and not comparison_mode:
        excel_path, db_path = save_outputs(df, audit_tables)
    else:
        excel_path, db_path = None, None
    return {
        "dataframe": df,
        "audit_tables": audit_tables,
        "comparison": comparison,
        "excel_path": excel_path,
        "db_path": db_path,
    }


####################################################
# MAIN
####################################################

if __name__ == "__main__":
    comparison_mode = (
        "--comparison" in sys.argv
        or os.environ.get(
            "CSAI_COMPARISON_MODE", ""
        ).strip().lower() in {"1", "true", "yes"}
    )
    result = run_event_aware_extraction(
        CLIENT_ROOT,
        persist=not comparison_mode,
        comparison_mode=comparison_mode,
    )
    print(result["dataframe"])
    print("\nDONE")
    if comparison_mode:
        print("Comparison mode: outputs were not replaced.")
    else:
        print(result["excel_path"])
        print(result["db_path"])
