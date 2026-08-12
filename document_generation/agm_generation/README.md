# Automated AGM Document Generator

This package generates AGM approval DOCX documents for the supported statutory
DWR authorities in the constitution database. It reads
the existing `csai_langchain` repositories in read-only mode; it does not modify
`csai_langchain` and does not use an LLM or RAG retrieval.

## Files and locations

- Production template: `C:\CSAI_OS\document_generation\templates\agm\agm_approve_accounts_template.docx`
- First/irregular-period template: `C:\CSAI_OS\document_generation\templates\agm\first_agm_approve_accounts_template.docx`
- Regulation 90 template: `C:\CSAI_OS\document_generation\templates\agm\agm_approve_accounts_template_section_90.docx`
- Program and tests: `C:\CSAI_OS\document_generation`
- Default generated output: `D:\CSAI_DATA\AGM Output`
- Preserved source template: `C:\CSAI_OS\03 Templates\AGM\template_test.doc`

## Usage

Run from `C:\CSAI_OS`:

```powershell
python -m document_generation.agm_generation --company "CS SURIA SDN. BHD."
```

Multiple companies are independent. An invalid company produces a complete
validation result without preventing valid companies from being generated:

```powershell
python -m document_generation.agm_generation `
  --company "CS SURIA SDN. BHD." `
  --company "CY GLOBAL INDUSTRIES SDN. BHD." `
  --overwrite
```

Useful options:

- `--dry-run`: retrieve and validate data without creating a DOCX.
- `--template PATH`: explicitly override automatic template selection.
- `--output-dir PATH`: change the output directory.
- `--output PATH`: set one output file; exactly one `--company` is required.
- `--overwrite`: replace an existing generated file.

The Python interface is:

```python
from document_generation import generate_documents

results = generate_documents(
    ["CS SURIA SDN. BHD."],
    template_path=None,
    output_dir=r"D:\CSAI_DATA\AGM Output",
    overwrite=False,
    dry_run=False,
    section90_inputs={"ATLAS AVENUE GOLD & JEWELLERY SDN. BHD.": "THIRTEENTH"},
)
```

Automatic selection first classifies the normalized DWR. Paragraph 15/Third
Schedule, Articles 23(b), 34, 36 and 37 of the Company’s Constitution, and
Regulation 34 of the Company’s Constitution use the first-AGM template when the
financial-period span is outside 364–367 days and otherwise use the standard
template. Regulation 90/Table A, Article 3(d), Clause 53, and Articles 5, 9, 72,
77 and 95 of the Company’s Articles of Association/Constitution always use the
Section 90 template and its complete workflow. Matching tolerates punctuation,
quote, spacing and optional-`TO` variants while keeping numbered authorities
distinct. Unknown DWR wording falls back to the standard template. An explicit
template path always wins. Section 90-family CLI runs prompt once per company
for an optional AGM ordinal; `--dry-run` reports that requirement without
pausing.

## Data sources

| Information | Existing repository/database |
|---|---|
| Company, registration number, directors, genders, members, addresses and shares | `CompanyRepository` / `csai_master.db:Client_Master` |
| Financial-year start/end, approval and circulation dates, declarant, statement signers, FS auditor and directors' fees | `FinancialStatementRepository` / `FS.db:FS` |
| DWR and MWR statutory clauses | `ConstitutionRepository` / `constitutions.db:Sheet1` |
| Auditor | `AuditorRepository` / `auditors.db:Sheet1` |
| Retiring directors | Checked names in the FYE-year column of the rotation workbook under `D:\CSAI_CLIENTS\<Folder>\AGM` |

The Client_Master match establishes the canonical company name before other
sources are queried. Registration numbers and auditor names are cross-checked
when the secondary source supplies them.

## Validation behavior

Generation is blocked for missing or ambiguous data, invalid date order,
missing director/member identities or member addresses, director/signatory
mismatches, duplicate identities, source cross-check failures, invalid fees or
fee shares, output collisions, and unresolved template markers. The temporary
DOCX is validated before it is moved to its final name.

For Templates 1/2, a positive FS fee uses only members who also match a Client_Master director as
eligible. Their shares are normalized over the eligible group. Currency uses
`Decimal`, two-decimal `ROUND_HALF_UP`, and a final-row remainder so the displayed
rows always equal the FS total. A null or zero fee removes the complete section
and renumbers the following DWR resolutions.

Template 3 intentionally has no fee or Authority-to-File resolution and does
not require an MWR clause. Its notice date is circulation date minus 18 days;
meeting and letter dates use the circulation date. Missing or ambiguous
rotation data blocks generation.

## Tests

```powershell
python -m unittest discover -s document_generation\tests -v
```

The suite also covers DWR variants, rotation discovery and validation, Section
90 prompting, derived dates, one through six people in every dynamic grid, and
the Section 90 NAME/SIGNATURE attendance register.
