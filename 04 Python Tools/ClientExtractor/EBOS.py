from pathlib import Path
from pypdf import PdfReader
import pandas as pd
import openpyxl
from openpyxl.styles import Font
import re
import warnings
from datetime import datetime
import sqlite3

warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")

CLIENT_ROOT = Path(r"D:\CSAI_CLIENTS")
OUTPUT_FILE = Path(r"D:\CSAI_DATA\Database\Ebos data.xlsx")
DB_DIR = Path(r"C:\CSAI_OS\04 Python Tools\DB")

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

    # Check for E-BOS / E-Bos / E-Bos folder
    ebos_folder = None
    for candidate in folder.iterdir():
        if candidate.is_dir() and candidate.name.upper().replace("-", "") == "EBOS":
            ebos_folder = candidate
            break

    if ebos_folder:
        pdfs = sorted(ebos_folder.rglob("*EBOS*"))
        if pdfs:
            return pdfs

    # Fallback: search whole folder
    return sorted(folder.rglob("*EBOS*"))


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

def save_to_sqlite(df, table_name):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db_path = DB_DIR / "ebos_master.db"
    conn = sqlite3.connect(str(db_path))
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"SQLite updated : {table_name}")


def write_ebos_sheet(writer, all_rows):
    """Write ALL companies' EBOS data to a single Excel sheet.
       Sorted by Client then PDF date. Auto-filter enabled."""

    if not all_rows:
        return

    df = pd.DataFrame(all_rows, columns=COLUMNS)

    # Sort by Client, then PDF Date
    df = df.sort_values(["Client", "PDF Date"], ascending=[True, True]).reset_index(drop=True)

    # Ensure string columns stored as strings (prevent Excel float .0 / leading zero loss)
    str_cols = ["IC", "Lodger IC", "Contact No", "Lodger Phone No", "Practising Cert No"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(x) if pd.notna(x) else ""
            )

    df.to_excel(writer, sheet_name="EBOS Data", index=False)

    if "UpdatedAt" not in df.columns:
        df["UpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_to_sqlite(df, "EBOS_Master")

    # Bold header + auto-filter
    wb = writer.book
    ws = wb["EBOS Data"]
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.auto_filter.ref = ws.dimensions


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

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nWriting Excel to {OUTPUT_FILE}...")

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        write_ebos_sheet(writer, all_rows)

    print("Done.")
    companies = len(set(r.get("Client", "") for r in all_rows))
    print(f"Total: {len(all_rows)} row(s) across {companies} company(ies).")


if __name__ == "__main__":
    main()
