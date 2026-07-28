from pathlib import Path
from pypdf import PdfReader
import pandas as pd
import re
import warnings
from datetime import datetime
import sqlite3

# Optional OCR support for scanned PDFs
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Suppress pypdf warnings (multiple categories emitted by pypdf internals)
warnings.filterwarnings("ignore", module="pypdf")
warnings.filterwarnings("ignore", category=UserWarning)

CLIENT_ROOT = Path(r"D:\CSAI_CLIENTS")
OUTPUT_FILE = Path(
    r"D:\CSAI_DATA\Database\clients_master.xlsx"
)
DB_DIR = Path(r"C:\CSAI_OS\04 Python Tools\DB")


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
    """Parse date string (dd/mm/yyyy or yyyy-mm-dd) to datetime."""
    try:
        if "-" in d:
            return datetime.strptime(d, "%Y-%m-%d")
        return datetime.strptime(d, "%d/%m/%Y")
    except:
        return None


def extract_submission_date(text):
    """Get the submission/lodgement date from SSM document."""
    patterns = [
        r'Submission Date\s+(\d{2}/\d{2}/\d{4})',
        r'Date of Lodgement\s+(\d{2}/\d{2}/\d{4})',
        r'Date of annual return\s+(\d{4}-\d{2}-\d{2})',
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            d = m.group(1)
            if "-" in d:
                dt = parse_date(d)
                return dt.strftime("%d/%m/%Y") if dt else d
            return d
    return ""


def extract_ref_date(text):
    """Extract date from SSM reference number (ROM/CPO/XBAR + DDMMYYYY)."""
    m = re.search(
        r'(?:ROM|CPO|XBAR)\s*(\d{2})(\d{2})(\d{4})',
        text,
        re.I
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
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
# SECTION 14 — INCORPORATION APPLICATION (FALLBACK)
####################################################

def find_section14(folder):
    best_pdf = None
    best_text = None
    best_has_regno = False

    for pdf in folder.rglob("*.pdf"):
        text = read_pdf(pdf)
        # If text is empty, try OCR (scanned PDFs)
        if not text.strip() and OCR_AVAILABLE:
            text = try_ocr_pdf(pdf)
            if text.strip():
                print(f"  OCR used for {pdf.name}")
        is_section14 = (
            "APPLICATION FOR REGISTRATION OF A COMPANY" in text.upper()
            or (
                bool(re.search(r'Section\s*14', text, re.I))
                and "PARTICULARS OF COMPANY" in text.upper()
            )
        )
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
    m = re.search(r'Incorporation\s+Date\s+(\d{2}/\d{2}/\d{4})', text, re.I)
    if m:
        return m.group(1)
    return ""


def try_ocr_pdf(pdf_path):
    """Attempt OCR on scanned PDF when text extraction yields nothing.
    Returns text or empty string."""
    if not OCR_AVAILABLE:
        return ""
    try:
        images = convert_from_path(str(pdf_path))
        text_parts = []
        for img in images:
            t = pytesseract.image_to_string(img)
            if t:
                text_parts.append(t)
        return "\n".join(text_parts)
    except Exception as e:
        print(f"  OCR failed for {pdf_path.name}: {e}")
        return ""


def find_section27_new_name(folder):
    """Find Section 27 (Change of Company Name) PDF and return new name."""
    for pdf in folder.rglob("*.pdf"):
        name = pdf.name.lower()
        if "section 27" not in name and "sec27" not in name:
            continue
        text = read_pdf(pdf)
        if "CHANGE OF NAME" not in text.upper() and "CHANGE OF COMPANY NAME" not in text.upper():
            continue
        # Try various patterns for new name
        for pat in [
            r'New\s+name\s+(.+?)(?:\n|$)',
            r'New\s+Company\s+Name\s+(.+?)(?:\n|$)',
            r'Name\s+of\s+Company\s+(.+?)(?:\n|$)',
        ]:
            m = re.search(pat, text, re.I)
            if m:
                new_name = clean(m.group(1))
                if new_name:
                    return new_name
    return ""


def find_incorporation_date_in_folder(folder):
    """Fallback: search key PDFs in folder for Incorporation Date.
    Only checks S14, S17, S51, S58 PDFs (most likely to contain incorporation info)."""
    for pdf in sorted(folder.rglob("*.pdf")):
        name = pdf.name.lower()
        if not any(kw in name for kw in ["section 14", "section 17", "section 51", "section 58",
                                           "sec14", "sec17", "sec51", "sec58",
                                           "superform 14"]):
            continue
        text = read_pdf(pdf)
        if not text.strip():
            text = try_ocr_pdf(pdf)
        if text:
            d = extract_incorporation_date(text)
            if d:
                return d
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
# MAIN
####################################################

if __name__ == "__main__":

    rows = []

    for folder in sorted(CLIENT_ROOT.iterdir()):
        if not folder.is_dir():
            continue
        print("Processing :", folder.name)

        pdf68 = latest_section68(folder)
        pdf14 = None
        text14 = None
        base_dt = None

        if pdf68:
            text68 = read_pdf(pdf68)
            s68_ar_date_str = annual_return_date(text68)
            base_dt = parse_date(s68_ar_date_str) if s68_ar_date_str else None

            row = {}
            row["Folder"] = folder.name
            co_name = company_name(text68)
            # Check Section 27 name change
            s27_name = find_section27_new_name(folder)
            if s27_name:
                print(f"  Section27 name: {co_name} → {s27_name}")
                co_name = s27_name
            row["Company Name"] = co_name
            row["Reg No"] = reg_no(text68)
            row["Annual Return Date"] = s68_ar_date_str or ""
            row["Incorporate Date"] = ""
            row["Total Issued Shares"] = ""
            row["Date of Lodgement"] = extract_submission_date(text68)
            row["Business Address"] = business_address(text68)
            row["Financial Record Address"] = financial_address(text68)

            directors = list(extract_directors(text68))
            members = list(extract_members(text68))
            total_shares = ""

            for s58_pdf, s58_text, s58_date_str, s58_dt in find_all_section58(folder):
                if base_dt and s58_dt and s58_dt <= base_dt:
                    continue
                for nd in extract_directors_section58(s58_text):
                    app_date = nd.get("Appointment Date", "")
                    app_dt = parse_date(app_date) if app_date else None
                    if app_dt and (base_dt is None or app_dt > base_dt):
                        ic58 = nd.get("IC", "")
                        if not any(d.get("IC", "") == ic58 for d in directors):
                            directors.append(nd)
                cess = extract_cessation_section58(s58_text)
                if cess:
                    cess_date = cess.get("Date of Cessation", "")
                    cess_dt = parse_date(cess_date) if cess_date else None
                    if cess_dt and (base_dt is None or cess_dt > base_dt):
                        ic58 = cess.get("IC", "")
                        name58 = cess.get("Name", "").strip().upper()
                        directors = [
                            d for d in directors
                            if not (d.get("IC", "") == ic58 and d.get("Name", "").upper() == name58)
                        ]

            #
            # Build director lookup for S51 member enrichment
            #
            director_lookup = {}
            for d in directors:
                ic = d.get("IC", "")
                if ic:
                    director_lookup[ic] = d

            pdf51, s51_date_str, s51_date_dt = find_latest_section51(folder)
            if pdf51:
                text51 = read_pdf(pdf51)
                members_51 = extract_members_section51(text51)
                # Use PDF-level date for priority decision
                s51_use = False
                if base_dt is None and members_51:
                    s51_use = True
                elif s51_date_dt is not None and base_dt is not None and s51_date_dt >= base_dt:
                    s51_use = True
                # Also check member-level dates (backward compatibility)
                if not s51_use:
                    s51_member_dates = [parse_date(m.get("Date", "")) for m in members_51 if m.get("Date")]
                    if s51_member_dates and (base_dt is None or max(s51_member_dates) >= base_dt):
                        s51_use = True
                if s51_use:
                    print(f"  Using Section51 (date {s51_date_str or 'N/A'})")
                    members = []
                    for m in members_51:
                        dir_info = director_lookup.get(m.get("IC", ""), {})
                        members.append({
                            "Type": m.get("Type", "INDIVIDUAL"),
                            "Name": m.get("Name", ""),
                            "ID Type": "MYKAD",
                            "ID No": m.get("IC", ""),
                            "Nationality": m.get("Nationality", "") or dir_info.get("Nationality", ""),
                            "Race": m.get("Race", "") or dir_info.get("Race", ""),
                            "Gender": dir_info.get("Gender", ""),
                            "DOB": dir_info.get("DOB", ""),
                            "Address": m.get("Address", ""),
                            "Shares": m.get("Shares", ""),
                            "Share Type": "ORDINARY SHARES",
                            "Analysis": "",
                            "Transferred In": m.get("Transferred In", ""),
                            "Transferred Out": m.get("Transferred Out", ""),
                            "Member Date": m.get("Date", ""),
                        })
                    total_shares = extract_total_shares_s51(text51)

            row["Total Issued Shares"] = total_shares or extract_total_shares(text68)

            pdf14, text14 = find_section14(folder)
            if text14:
                row["Incorporate Date"] = extract_incorporation_date(text14) or ""
            if not row.get("Incorporate Date"):
                # Fallback: search key PDFs in folder
                fallback = find_incorporation_date_in_folder(folder)
                if fallback:
                    row["Incorporate Date"] = fallback

        elif not pdf68:
            pdf14, text14 = find_section14(folder)
            if not pdf14:
                print("  No Section68 or Section14 found.")
                continue

            print(f"  Using Section14 ({pdf14.name})")

            co = extract_company_section14(text14)
            row = {}
            row["Folder"] = folder.name
            co_name = co["name"]
            # Check Section 27 name change
            s27_name = find_section27_new_name(folder)
            if s27_name:
                print(f"  Section27 name: {co_name} → {s27_name}")
                co_name = s27_name
            row["Company Name"] = co_name
            row["Reg No"] = co["reg_no"]
            inc_date = extract_incorporation_date(text14)
            inc_dt = parse_date(inc_date) if inc_date else None
            row["Annual Return Date"] = ""
            row["Incorporate Date"] = inc_date or ""
            if not row["Incorporate Date"]:
                fallback = find_incorporation_date_in_folder(folder)
                if fallback:
                    row["Incorporate Date"] = fallback
            base_dt = inc_dt
            if inc_dt:
                try:
                    ar_dt_calc = inc_dt.replace(year=inc_dt.year + 1)
                    row["Annual Return Date"] = ar_dt_calc.strftime("%d/%m/%Y")
                except ValueError:
                    pass
            row["Total Issued Shares"] = extract_total_shares_section14(text14)
            row["Date of Lodgement"] = extract_submission_date(text14)
            row["Business Address"] = co["business_address"]
            row["Financial Record Address"] = co["registered_address"]

            directors = list(extract_directors_section14(text14))
            members = list(extract_members_section14(text14))
            for m in members:
                m["Type"] = "INDIVIDUAL"
                m["Gender"] = ""
                m["Analysis"] = ""
                if not m.get("ID Type"):
                    m["ID Type"] = "MYKAD"

            for s58_pdf, s58_text, s58_date_str, s58_dt in find_all_section58(folder):
                if base_dt and s58_dt and s58_dt <= base_dt:
                    continue
                for nd in extract_directors_section58(s58_text):
                    app_date = nd.get("Appointment Date", "")
                    app_dt = parse_date(app_date) if app_date else None
                    if app_dt and (base_dt is None or app_dt > base_dt):
                        ic58 = nd.get("IC", "")
                        if not any(d.get("IC", "") == ic58 for d in directors):
                            directors.append(nd)
                cess = extract_cessation_section58(s58_text)
                if cess:
                    cess_date = cess.get("Date of Cessation", "")
                    cess_dt = parse_date(cess_date) if cess_date else None
                    if cess_dt and (base_dt is None or cess_dt > base_dt):
                        ic58 = cess.get("IC", "")
                        name58 = cess.get("Name", "").strip().upper()
                        directors = [
                            d for d in directors
                            if not (d.get("IC", "") == ic58 and d.get("Name", "").upper() == name58)
                        ]

            #
            # Build director lookup for S51 member enrichment
            #
            director_lookup = {}
            for d in directors:
                ic = d.get("IC", "")
                if ic:
                    director_lookup[ic] = d

            pdf51, s51_date_str, s51_date_dt = find_latest_section51(folder)
            if pdf51:
                text51 = read_pdf(pdf51)
                members_51 = extract_members_section51(text51)
                # Use PDF-level date for priority decision
                s51_use = False
                if base_dt is None and members_51:
                    s51_use = True
                elif s51_date_dt is not None and base_dt is not None and s51_date_dt >= base_dt:
                    s51_use = True
                # Also check member-level dates (backward compatibility)
                if not s51_use:
                    s51_member_dates = [parse_date(m.get("Date", "")) for m in members_51 if m.get("Date")]
                    if s51_member_dates and (base_dt is None or max(s51_member_dates) >= base_dt):
                        s51_use = True
                if s51_use:
                    print(f"  Using Section51 (date {s51_date_str or 'N/A'})")
                    members = []
                    for m in members_51:
                        dir_info = director_lookup.get(m.get("IC", ""), {})
                        members.append({
                            "Type": m.get("Type", "INDIVIDUAL"),
                            "Name": m.get("Name", ""),
                            "ID Type": "MYKAD",
                            "ID No": m.get("IC", ""),
                            "Nationality": m.get("Nationality", "") or dir_info.get("Nationality", ""),
                            "Race": m.get("Race", "") or dir_info.get("Race", ""),
                            "Gender": dir_info.get("Gender", ""),
                            "DOB": dir_info.get("DOB", ""),
                            "Address": m.get("Address", ""),
                            "Shares": m.get("Shares", ""),
                            "Share Type": "ORDINARY SHARES",
                            "Analysis": "",
                            "Transferred In": m.get("Transferred In", ""),
                            "Transferred Out": m.get("Transferred Out", ""),
                            "Member Date": m.get("Date", ""),
                        })
                    row["Total Issued Shares"] = extract_total_shares_s51(text51) or row["Total Issued Shares"]

        else:
            continue

        for i, d in enumerate(directors, start=1):
            row[f"Director{i} Name"] = d.get("Name", "")
            row[f"Director{i} IC"] = d.get("IC", "")
            row[f"Director{i} DOB"] = d.get("DOB", "")
            row[f"Director{i} Nationality"] = d.get("Nationality", "")
            row[f"Director{i} Race"] = d.get("Race", "")
            row[f"Director{i} Gender"] = d.get("Gender", "")
            row[f"Director{i} Residential Address"] = d.get("Residential", "")
            row[f"Director{i} Service Address"] = d.get("Service Address", "")

        row["_members"] = members
        rows.append(row)

    ####################################################
    # EXPORT
    ####################################################

    max_members = max(
        (len(r.get("_members", [])) for r in rows),
        default=0
    )

    MEMBER_FIELDS = [
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

    for r in rows:
        members = r.pop("_members", [])
        for j in range(max_members):
            prefix = f"Member{j + 1}"
            if j < len(members):
                m = members[j]
                for col_key, dict_key in MEMBER_FIELDS:
                    r[f"{prefix} {col_key}"] = m.get(dict_key, "")
            else:
                for col_key, dict_key in MEMBER_FIELDS:
                    r[f"{prefix} {col_key}"] = ""

    df = pd.DataFrame(rows)

    string_cols = [
        c for c in df.columns
        if "IC" in c or "ID No" in c
    ]

    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(int(x)) if pd.notna(x) and isinstance(x, float) and x == int(x) else str(x) if pd.notna(x) else ""
            )

    df.to_excel(OUTPUT_FILE, index=False)
    if "UpdatedAt" not in df.columns:
        df["UpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_to_sqlite(df, "Client_Master")

    print(df)
    print("\nDONE")
    print(OUTPUT_FILE)