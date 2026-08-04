from pathlib import Path
from pypdf import PdfReader
import pandas as pd
from collections import Counter
import re
import warnings
from datetime import datetime
import sqlite3
import os
import shutil

warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")

CLIENT_ROOT = Path(r"D:\CSAI_CLIENTS")
OUTPUT_FILE = Path(r"D:\CSAI_DATA\Database\Ebos data.xlsx")
DB_DIR = Path(
    os.environ.get(
        "CSAI_DB_DIR",
        r"C:\CSAI_OS\06 Data\databases",
    )
)

# All columns in output order
COLUMNS = [
    # Source
    "Source PDF",
    "PDF Date",
    "Client",
    # Header
    "Submission No",
    "Date Received",
    "Time Received",
    # Company
    "Company Name",
    "Company No",
    "Company Status",
    # BO Identification
    "BO Status",
    "Date of Becoming BO",
    "Date of Cessation",
    "Reason",
    "Date of Data Recorded",
    # Person
    "Type",
    "Category",
    "Name",
    "IC",
    "DOB",
    "Gender",
    "Race",
    "Nationality",
    "Citizenship",
    "Designation",
    "Residential Address",
    "Business Address",
    "Email",
    "Contact No",
    # Ownership
    "Type of BO",
    "Criteria A - Direct Ownership %",
    "Criteria B - Voting Shares %",
    "Criteria C - N/A",
    # Declaration
    "Declaration Name",
    "Date of Application",
    # Lodger
    "Lodger Name",
    "Lodger IC",
    "Lodger Address",
    "Lodger Email",
    "Lodger Phone No",
    "Practising Cert No",
    "Professional Body Type",
    "License / Membership No",
]

BASE_COLUMNS = [
    "Company",
    "Company Name",
    "Company No",
    "Company Status",
]

EVENT_COLUMNS = [
    column
    for column in COLUMNS
    if column != "Client"
]

EVENT_DATE_PRIORITY = [
    "Date Received",
    "PDF Date",
    "Date of Application",
    "Date of Data Recorded",
]


####################################################
# PDF READER
####################################################

def read_pdf(pdf):

    text = ""

    try:

        reader = PdfReader(pdf)

        for page in reader.pages:

            t = page.extract_text()

            if t:
                text += "\n" + t

    except Exception as e:

        print("PDF ERROR :", pdf)
        print(e)

    text = text.replace("\xa0", " ")

    return text


####################################################
# EBOS IDENTIFIER
####################################################

def is_ebos(text):
    """Check if text contains EBOS header."""
    return "Division 8A, 60B (3), Companies Act 2016" in text


####################################################
# HEADER INFO
####################################################

def extract_header_info(text):

    result = {
        "Submission No": "",
        "Date Received": "",
        "Time Received": "",
    }

    m = re.search(
        r'Submission Number\s+(\S+)',
        text
    )

    if m:
        result["Submission No"] = m.group(1)

    m = re.search(
        r'Date & Time Received\s+(\d{2}/\d{2}/\d{4})\s+(\S+)',
        text
    )

    if m:
        result["Date Received"] = m.group(1)
        result["Time Received"] = m.group(2)

    return result


####################################################
# COMPANY INFO
####################################################

def extract_company_info(text):

    result = {
        "Company Name": "",
        "Company No": "",
        "Company Status": "",
    }

    m = re.search(
        r'COMPANY NAME\s+(.+?)(?:\n|$)',
        text,
        re.I
    )

    if m:
        result["Company Name"] = m.group(1).strip()

    m = re.search(
        r'COMPANY NO\s+(.+?)(?:\n|$)',
        text,
        re.I
    )

    if m:
        result["Company No"] = m.group(1).strip()

    m = re.search(
        r'STATUS\s+(.+?)(?:\n|$)',
        text,
        re.I
    )

    if m:
        result["Company Status"] = m.group(1).strip()

    return result


####################################################
# BO BLOCK SPLITTER
####################################################

def split_bo_blocks(text):
    """Split text on PARTICULARS OF BENEFICIAL OWNERSHIP marker.
       First part is header + company info, skip it."""

    parts = re.split(
        r'PARTICULARS\s+OF\s+BENEFICIAL\s+OWNERSHIP',
        text,
        flags=re.I
    )

    return [p.strip() for p in parts[1:] if p.strip()]


####################################################
# BO FIELD EXTRACTOR
####################################################

def extract_bo_fields(block):

    fields = {}

    def get(key, pat, multiline=False, flag_repl=True):
        flags = re.I | (re.S if multiline else 0)
        m = re.search(pat, block, flags)
        if m:
            val = m.group(1).strip()
            if multiline and flag_repl:
                val = re.sub(r'\s+', ' ', val)
            fields[key] = val

    get("BO Status", r'STATUS\s+(NEW|CESSATION)')
    get("Date of Becoming BO", r'DATE\s+OF\s+BECOMING\s+BO\s+(\d{2}/\d{2}/\d{4})')
    get("Date of Cessation", r'DATE\s+OF\s+CESSATION\s+(\d{2}/\d{2}/\d{4})')
    get("Reason",
        r'REASON\s+(.+?)(?:\nTYPE|\nCATEGORY|\nNAME|$)',
        multiline=True)
    get("Date of Data Recorded",
        r'DATE\s+OF\s+DATA\s+RECORDED\s+(\d{2}/\d{2}/\d{4})')
    get("Type",
        r'\nTYPE\s+(INDIVIDUAL|COMPANY|BODY\s+CORPORATE|NOMINEE)',
        multiline=False, flag_repl=False)
    get("Category",
        r'CATEGORY\s+(.+?)(?:\n|$)',
        multiline=True)
    get("Name",
        r'NAME\s+(.+?)(?:\n|IDENTIFICATION)',
        multiline=True)
    get("IC", r'IDENTIFICATION\s+NO\.?\s+(\d{12})')
    get("DOB", r'DATE\s+OF\s+BIRTH\s+(\d{2}/\d{2}/\d{4})')
    get("Gender", r'GENDER\s+(MALE|FEMALE)')
    get("Race", r'RACE\s+([A-Z]+)')
    get("Nationality",
        r'NATIONALITY\s+([A-Z\s]+?)(?:\s+CITIZENSHIP|\n|$)',
        multiline=True)
    get("Citizenship",
        r'CITIZENSHIP\s+([A-Z\s]+?)(?:\n|$)',
        multiline=True)
    get("Designation",
        r'DESIGNATION/POSITION\s+IN\s+THE\s+COMPANY\s+(.+?)(?:\nRESIDENTIAL|\nBUSINESS)',
        multiline=True)
    get("Residential Address",
        r'RESIDENTIAL\s+ADDRESS\s+(.+?)(?:\nBUSINESS|\nEMAIL)',
        multiline=True)
    get("Business Address",
        r'BUSINESS\s+ADDRESS\s+(.+?)(?:\nEMAIL|\nCONTACT)',
        multiline=True)
    get("Email", r'EMAIL\s+(\S+@\S+)')
    get("Contact No", r'CONTACT\s+NO\.?\s+(\S+)')
    get("Type of BO",
        r'TYPE\s+OF\s+BO\s+(?!APPLICATION)(.+?)(?:\n|Criteria)',
        multiline=True)
    get("Criteria A - Direct Ownership %",
        r'Criteria\s+A\s*[-:]\s*Direct\s+Ownership[:\s]*([\d.]+)')
    get("Criteria B - Voting Shares %",
        r'Criteria\s+B\s*[-:]\s*Voting\s+Shares[:\s]*([\d.]+)')
    get("Criteria C - N/A",
        r'Criteria\s+C\s*[-:]\s*([\d.]+|N/A)')

    return fields


####################################################
# DECLARATION EXTRACTOR
####################################################

def extract_declaration_info(text):
    """Extract Declaration section: Name, Date of Application."""

    result = {
        "Declaration Name": "",
        "Date of Application": "",
    }

    # Find DECLARATION block
    m = re.search(
        r'DECLARATION\s+(.*?)(?:ATTENTION|LODGER)',
        text, re.I | re.S
    )

    if not m:
        return result

    decl_block = m.group(1)

    m2 = re.search(r'NAME\s+(.+?)(?:\n|$)', decl_block, re.I)
    if m2:
        result["Declaration Name"] = m2.group(1).strip()

    m2 = re.search(
        r'DATE\s+OF\s+APPLICATION\s+(\d{2}/\d{2}/\d{4})',
        decl_block, re.I
    )
    if m2:
        result["Date of Application"] = m2.group(1).strip()

    return result


####################################################
# LODGER EXTRACTOR
####################################################

def extract_lodger_info(text):
    """Extract Lodger Information section."""

    result = {
        "Lodger Name": "",
        "Lodger IC": "",
        "Lodger Address": "",
        "Lodger Email": "",
        "Lodger Phone No": "",
        "Practising Cert No": "",
        "Professional Body Type": "",
        "License / Membership No": "",
    }

    # Find LODGER INFORMATION block
    m = re.search(
        r'LODGER\s+INFORMATION\s+(.*?)(?:SURUHANJAYA|$)',
        text, re.I | re.S
    )

    if not m:
        return result

    lodger_block = m.group(1)

    m2 = re.search(r'NAME\s+(.+?)(?:\n|$)', lodger_block, re.I)
    if m2:
        result["Lodger Name"] = m2.group(1).strip()

    m2 = re.search(
        r'IDENTIFICATION\s+NO\.?\s+(\d{12})',
        lodger_block, re.I
    )
    if m2:
        result["Lodger IC"] = m2.group(1)

    m2 = re.search(
        r'ADDRESS\s+(.+?)(?:\nEMAIL|\nPHONE|\nPRACTISING|\nPROFESSIONAL|\nLICENSE)',
        lodger_block, re.I | re.S
    )
    if m2:
        addr = re.sub(r'\s+', ' ', m2.group(1)).strip()
        result["Lodger Address"] = addr

    m2 = re.search(
        r'EMAIL\s+ADDRESS\s+(\S+)',
        lodger_block, re.I
    )
    if m2:
        result["Lodger Email"] = m2.group(1)

    m2 = re.search(
        r'PHONE\s+NO\.?\s+(\S+)',
        lodger_block, re.I
    )
    if m2:
        result["Lodger Phone No"] = m2.group(1)

    m2 = re.search(
        r'PRACTISING\s+CERTIFICATE\s+NO\.?\s+(\S+)',
        lodger_block, re.I
    )
    if m2:
        result["Practising Cert No"] = m2.group(1)

    m2 = re.search(
        r'PROFESSIONAL\s+BODY\s+TYPE\s+(.+?)(?:\n|$)',
        lodger_block, re.I
    )
    if m2:
        result["Professional Body Type"] = m2.group(1).strip()

    m2 = re.search(
        r'LICENSE\s+NO\.?\s*[/,]\s*MEMBERSHIP\s+NO\.?\s+(\S+(?:\s+\S+)?)',
        lodger_block, re.I
    )
    if m2:
        result["License / Membership No"] = m2.group(1)

    return result


####################################################
# FIND EBOS PDFs
####################################################

def find_ebos_pdfs(folder):
    """Find EBOS PDFs. Prefer E-BOS/E-Bos folder if exists."""

    def matching_pdfs(search_root):

        return sorted(
            path
            for path in search_root.rglob("*")
            if (
                path.is_file()
                and path.suffix.lower() == ".pdf"
                and "EBOS" in path.name.upper()
            )
        )

    # Check for E-BOS / E-Bos / E-Bos folder
    ebos_folder = None
    for candidate in folder.iterdir():
        if candidate.is_dir() and candidate.name.upper().replace("-", "") == "EBOS":
            ebos_folder = candidate
            break

    if ebos_folder:
        pdfs = matching_pdfs(
            ebos_folder
        )
        if pdfs:
            return pdfs

    # Fallback: search whole folder
    return matching_pdfs(
        folder
    )


####################################################
# DATE PARSER
####################################################

def parse_date_safe(d):
    try:
        return datetime.strptime(d, "%d/%m/%Y")
    except:
        return None


def extract_pdf_date(text, pdf_name):
    """Get the best date for this PDF (for sorting)."""
    # Try header Date Received
    m = re.search(r'Date & Time Received\s+(\d{2}/\d{2}/\d{4})', text)
    if m:
        dt = parse_date_safe(m.group(1))
        if dt:
            return dt
    # Try Date of Application from Declaration
    m = re.search(r'DATE\s+OF\s+APPLICATION\s+(\d{2}/\d{2}/\d{4})', text, re.I)
    if m:
        dt = parse_date_safe(m.group(1))
        if dt:
            return dt
    # Fallback: date from filename (YYYMMDD pattern)
    m = re.search(r'(\d{4})(\d{2})(\d{2})', pdf_name)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except:
            pass
    return datetime.min


####################################################
# PROCESS ONE PDF
####################################################

def process_pdf(pdf):
    """Extract all data from one EBOS PDF.
       Returns (pdf_name_str, date_dt, [row_dict, ...]) or None."""

    text = read_pdf(pdf)
    if not is_ebos(text):
        return None

    header = extract_header_info(text)
    company = extract_company_info(text)
    declaration = extract_declaration_info(text)
    lodger = extract_lodger_info(text)

    pdf_name = pdf.name
    pdf_date = extract_pdf_date(text, pdf_name)
    pdf_date_str = pdf_date.strftime("%d/%m/%Y") if pdf_date and pdf_date != datetime.min else ""

    bo_blocks = split_bo_blocks(text)
    rows = []

    for block in bo_blocks:
        bo = extract_bo_fields(block)
        if not bo.get("IC"):
            continue

        # Build flat row with ALL fields
        row = {}

        # Source
        row["Source PDF"] = pdf_name
        row["PDF Date"] = pdf_date_str

        # Header
        row["Submission No"] = header.get("Submission No", "")
        row["Date Received"] = header.get("Date Received", "")
        row["Time Received"] = header.get("Time Received", "")

        # Company
        row["Company Name"] = company.get("Company Name", "")
        row["Company No"] = company.get("Company No", "")
        row["Company Status"] = company.get("Company Status", "")

        # BO fields
        for key in [
            "BO Status", "Date of Becoming BO", "Date of Cessation", "Reason",
            "Date of Data Recorded", "Type", "Category", "Name", "IC", "DOB",
            "Gender", "Race", "Nationality", "Citizenship", "Designation",
            "Residential Address", "Business Address", "Email", "Contact No",
            "Type of BO",
            "Criteria A - Direct Ownership %",
            "Criteria B - Voting Shares %",
            "Criteria C - N/A",
        ]:
            row[key] = bo.get(key, "")

        # Declaration
        row["Declaration Name"] = declaration.get("Declaration Name", "")
        row["Date of Application"] = declaration.get("Date of Application", "")

        # Lodger
        for key in [
            "Lodger Name", "Lodger IC", "Lodger Address", "Lodger Email",
            "Lodger Phone No", "Practising Cert No", "Professional Body Type",
            "License / Membership No",
        ]:
            row[key] = lodger.get(key, "")

        rows.append(row)

    return pdf_name, pdf_date, rows


####################################################
# EBOS SHEET WRITER
####################################################

def clean_value(value):
    """Return a stable text value, treating missing values as blank."""

    if value is None or pd.isna(value):
        return ""

    return str(value).strip()


def normalize_key(value):
    """Normalize a company identity fallback without changing display text."""

    value = clean_value(value).upper()
    value = re.sub(r"[^A-Z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_event_date(row):
    """Return the first usable event date based on filing-date priority."""

    for column in EVENT_DATE_PRIORITY:
        value = clean_value(row.get(column))

        if not value:
            continue

        parsed = pd.to_datetime(
            value,
            errors="coerce",
            dayfirst=True,
        )

        if not pd.isna(parsed):
            return parsed.to_pydatetime()

    return None


def event_sort_key(row):
    """Sort newest dated events first and undated events last."""

    parsed = parse_event_date(row)

    return (
        0 if parsed else 1,
        -parsed.timestamp() if parsed else 0,
        clean_value(row.get("Submission No")).upper(),
        clean_value(row.get("Source PDF")).upper(),
    )


def most_frequent_value(rows, column):
    """Choose the most frequent spelling, using first occurrence as a tie-break."""

    values = [
        clean_value(row.get(column))
        for row in rows
        if clean_value(row.get(column))
    ]

    if not values:
        return ""

    counts = Counter(values)
    highest_count = max(counts.values())

    return next(
        value
        for value in values
        if counts[value] == highest_count
    )


def event_fingerprint(row):
    """Identify one logical BO event while ignoring duplicate source filenames."""

    return tuple(
        clean_value(row.get(column))
        for column in EVENT_COLUMNS
        if column != "Source PDF"
    )


def company_group_key(row):
    """Use registration number as company identity, with safe fallbacks."""

    company_no = clean_value(row.get("Company No"))

    if company_no:
        return f"REG:{company_no.upper()}"

    company = normalize_key(row.get("Client"))

    if company:
        return f"COMPANY:{company}"

    return (
        "NAME:"
        + normalize_key(row.get("Company Name"))
    )


def consolidate_ebos_rows(all_rows):
    """Convert the long event list into one wide row per registered company."""

    groups = {}

    for original_row in all_rows:
        row = {
            column: clean_value(
                original_row.get(column)
            )
            for column in COLUMNS
        }

        key = company_group_key(row)
        groups.setdefault(key, []).append(row)

    consolidated_groups = []
    raw_event_count = len(all_rows)
    logical_event_count = 0
    maximum_event_count = 0

    for rows in groups.values():
        logical_events = {}

        for row in rows:
            fingerprint = event_fingerprint(row)
            existing = logical_events.get(
                fingerprint
            )

            if (
                existing is None
                or clean_value(
                    row.get("Source PDF")
                ).upper()
                < clean_value(
                    existing.get("Source PDF")
                ).upper()
            ):
                logical_events[
                    fingerprint
                ] = row

        events = sorted(
            logical_events.values(),
            key=event_sort_key,
        )

        logical_event_count += len(events)
        maximum_event_count = max(
            maximum_event_count,
            len(events),
        )

        latest_named_event = next(
            (
                event
                for event in events
                if clean_value(
                    event.get("Company Name")
                )
            ),
            {},
        )

        latest_status_event = next(
            (
                event
                for event in events
                if clean_value(
                    event.get("Company Status")
                )
            ),
            {},
        )

        consolidated_groups.append({
            "base": {
                "Company": most_frequent_value(
                    rows,
                    "Client",
                ),
                "Company Name": clean_value(
                    latest_named_event.get(
                        "Company Name"
                    )
                ),
                "Company No": most_frequent_value(
                    rows,
                    "Company No",
                ),
                "Company Status": clean_value(
                    latest_status_event.get(
                        "Company Status"
                    )
                ),
            },
            "events": events,
        })

    columns = list(BASE_COLUMNS)

    for index in range(
        1,
        maximum_event_count + 1,
    ):
        columns.extend(
            f"BO{index} {column}"
            for column in EVENT_COLUMNS
        )

    columns.append("UpdatedAt")
    updated_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    output_rows = []

    for group in consolidated_groups:
        output_row = dict(group["base"])

        for index, event in enumerate(
            group["events"],
            start=1,
        ):
            for column in EVENT_COLUMNS:
                output_row[
                    f"BO{index} {column}"
                ] = clean_value(
                    event.get(column)
                )

        output_row["UpdatedAt"] = updated_at
        output_rows.append(output_row)

    output_rows.sort(
        key=lambda row: (
            normalize_key(
                row.get("Company Name")
            ),
            clean_value(
                row.get("Company No")
            ),
        )
    )

    dataframe = pd.DataFrame(
        output_rows,
        columns=columns,
    )

    dataframe = dataframe.replace(
        {
            "": None,
        }
    )

    statistics = {
        "raw_events": raw_event_count,
        "logical_events": logical_event_count,
        "duplicates_removed": (
            raw_event_count
            - logical_event_count
        ),
        "company_rows": len(output_rows),
        "maximum_bo_slots": maximum_event_count,
    }

    return dataframe, statistics


def write_excel_atomic(dataframe):
    """Atomically replace the EBOS workbook with the consolidated output."""

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = OUTPUT_FILE.with_name(
        f".{OUTPUT_FILE.stem}.tmp.xlsx"
    )

    if temp_path.exists():
        temp_path.unlink()

    try:
        dataframe.to_excel(
            temp_path,
            sheet_name="EBOS Data",
            index=False,
        )

        os.replace(
            temp_path,
            OUTPUT_FILE,
        )

    finally:
        if temp_path.exists():
            temp_path.unlink()


def validate_output_paths():
    """Prevent the Excel workbook from overwriting the SQLite database."""

    database_path = DB_DIR / "ebos_master.db"

    if OUTPUT_FILE.suffix.lower() != ".xlsx":
        raise ValueError(
            "The EBOS workbook output must use an .xlsx extension: "
            f"{OUTPUT_FILE}"
        )

    if database_path.suffix.lower() != ".db":
        raise ValueError(
            "The EBOS database output must use a .db extension: "
            f"{database_path}"
        )

    workbook_path = os.path.normcase(
        str(OUTPUT_FILE.resolve(strict=False))
    )
    sqlite_path = os.path.normcase(
        str(database_path.resolve(strict=False))
    )

    if workbook_path == sqlite_path:
        raise ValueError(
            "The EBOS workbook and SQLite database must use separate files."
        )


def replace_sqlite_table_transactional(
    dataframe,
    database_path,
    table_name,
):
    """Swap a validated staging table when Windows locks the database file."""

    staging_table = (
        f"__sync_{table_name}"
    )
    connection = sqlite3.connect(
        str(database_path),
        timeout=30,
    )

    try:
        connection.execute(
            f"DROP TABLE IF EXISTS [{staging_table}]"
        )
        connection.commit()

        dataframe.to_sql(
            staging_table,
            connection,
            if_exists="replace",
            index=False,
        )

        staging_columns = [
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info([{staging_table}])"
            )
        ]
        staging_rows = connection.execute(
            f"SELECT COUNT(*) FROM [{staging_table}]"
        ).fetchone()[0]

        if staging_columns != list(dataframe.columns):
            raise RuntimeError(
                f"Column validation failed for {table_name}."
            )

        if staging_rows != len(dataframe):
            raise RuntimeError(
                f"Row-count validation failed for {table_name}: "
                f"expected {len(dataframe)}, imported "
                f"{staging_rows}."
            )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )
            connection.execute(
                f"DROP TABLE IF EXISTS [{table_name}]"
            )
            connection.execute(
                f"ALTER TABLE [{staging_table}] "
                f"RENAME TO [{table_name}]"
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    finally:
        try:
            connection.execute(
                f"DROP TABLE IF EXISTS [{staging_table}]"
            )
            connection.commit()
        finally:
            connection.close()


def save_to_sqlite_atomic(
    dataframe,
    table_name,
):
    """Atomically replace one SQLite table while preserving other tables."""

    DB_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    database_path = (
        DB_DIR
        / "ebos_master.db"
    )
    temp_path = (
        DB_DIR
        / ".ebos_master.tmp.db"
    )

    if temp_path.exists():
        temp_path.unlink()

    if database_path.exists():
        shutil.copy2(
            database_path,
            temp_path,
        )

    try:
        connection = sqlite3.connect(
            str(temp_path)
        )

        try:
            with connection:
                dataframe.to_sql(
                    table_name,
                    connection,
                    if_exists="replace",
                    index=False,
                )
        finally:
            connection.close()

        try:
            os.replace(
                temp_path,
                database_path,
            )
        except PermissionError:
            replace_sqlite_table_transactional(
                dataframe,
                database_path,
                table_name,
            )

    finally:
        if temp_path.exists():
            temp_path.unlink()

    print(
        "SQLite updated : "
        f"{database_path} ({table_name})"
    )


####################################################
# PROCESS COMPANY
####################################################

def process_company(folder):
    """Find and process all EBOS PDFs in a company folder.
       Returns list of (pdf_name, pdf_date, [rows]) per PDF."""

    pdfs = find_ebos_pdfs(folder)
    if not pdfs:
        return None

    pdf_results = []

    for pdf in pdfs:
        result = process_pdf(pdf)
        if result:
            pdf_results.append(result)

    return pdf_results if pdf_results else None


####################################################
# MAIN
####################################################

def main():

    validate_output_paths()

    print("EBOS Extractor")
    print("=" * 40)
    print(f"Input root: {CLIENT_ROOT}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    all_rows = []

    for folder in sorted(CLIENT_ROOT.iterdir()):

        if not folder.is_dir():
            continue

        print(f"Processing: {folder.name}")

        result = process_company(folder)

        if result is None:
            print("  No EBOS data found.")
            continue

        total_pdfs = len(result)
        total_bo = 0

        for pdf_name, pdf_date, bo_rows in result:
            total_bo += len(bo_rows)
            for row in bo_rows:
                row["Client"] = folder.name
                all_rows.append(row)

        print(f"  {total_pdfs} PDF(s), {total_bo} BO entry(ies).")

    if not all_rows:
        print("No company data to export.")
        return

    dataframe, statistics = (
        consolidate_ebos_rows(
            all_rows
        )
    )

    print()
    print(
        "Raw BO events        :",
        statistics["raw_events"],
    )
    print(
        "Logical BO events    :",
        statistics["logical_events"],
    )
    print(
        "Duplicates removed   :",
        statistics["duplicates_removed"],
    )
    print(
        "Company rows         :",
        statistics["company_rows"],
    )
    print(
        "Maximum BO slots     :",
        statistics["maximum_bo_slots"],
    )

    print(
        f"\nWriting Excel to {OUTPUT_FILE}..."
    )

    write_excel_atomic(
        dataframe
    )

    save_to_sqlite_atomic(
        dataframe,
        "EBOS_Master",
    )

    print("Done.")
    print(
        "Total: "
        f"{statistics['company_rows']} "
        "company row(s), "
        f"{statistics['logical_events']} "
        "logical BO event(s)."
    )


if __name__ == "__main__":
    main()
