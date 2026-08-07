# AGM production template contract

## Authority and preservation

The production template combines the standardized wording and layout selected
from:

- `C:\CSAI_OS\03 Templates\AGM\template_test.doc`
- `D:\CSAI_CLIENTS\AGENSI SUPREME LOGISTIC SDN. BHD\AGM\Agensi Supreme Logistic - Approve Accounts YE30.09.2025 (2026).doc`
- `D:\CSAI_CLIENTS\CS SURIA SDN. BHD\AGM\CS SURIA - Approve_Directors'_Report_2025 (2026).doc`

The legacy `template_test.doc` is preserved unchanged. Its recorded SHA-256 at
implementation time is
`25A62483AB3DD1AD43A295864B5EBC5A0BF54C1C1E05E0C3412217E8FD976919`.

The deployable template is
`C:\CSAI_OS\document_generation\templates\agm_approve_accounts_template.docx`.
It is A4 portrait and retains the source document's Times New Roman typography.
All sections retain the safe 0.5-inch top margin. On the DWR and MWR pages, the
three-line company/registration/incorporation block uses a 1 cm smaller leading
offset and an equal compensating space below the block, so the block moves up
without moving the resolution title or body. DWR, MWR, and the letter are
separate Word sections beginning on a new page, so an earlier section may
expand without disturbing a later page start.

The canonical irregular-period template is
`C:\CSAI_OS\document_generation\templates\first_agm_approve_accounts_template.docx`.
It is selected independently for each company when the literal Python date
difference `(financial_year_end - financial_year_start).days` is less than 364
or greater than 367. Periods from 364 through 367 days inclusive use the
standard template. An explicitly supplied `template_path` or CLI `--template`
always overrides this automatic selection.

The six-page Regulation 90 template is
`C:\CSAI_OS\document_generation\templates\agm_approve_accounts_template_section_90.docx`.
It contains independent new-page DWR, Notice, Minutes, Attendance, letter, and
acknowledgement sections. It intentionally omits the director-fee and
Authority-to-File resolutions and does not require an MWR clause.

## Scalar markers

- `{{ company_name }}`
- `{{ registration_no }}`
- `{{ dwr_clause }}` and `{{ mwr_clause }}`
- `{{ financial_year_start }}` (used by the irregular-period template)
- `{{ financial_year_end }}` and `{{ financial_year_end_upper }}`
- `{{ board_approval_date }}`, `{{ circulation_date }}`, `{{ lapse_date }}`
- `{{ statement_signers_with_titles }}` and `{{ statement_signer_authority }}`
- `{{ declarant_with_title }}` and `{{ declarant_name_upper }}`
- `{{ auditor_name }}`
- `{{ circulation_section_number }}` and `{{ filing_section_number }}`
- `{{ director_signature_heading }}`, `{{ member_signature_heading }}`,
  `{{ shareholder_heading }}`, and `{{ salutation }}`
- Section 90 AGM title, meeting/notice/letter dates, venue and times, chair,
  retiring-director names, and singular/plural grammar markers

## Block markers

- `{{ block:director_fee_section }}`
- `{{ block:director_signatures }}`
- `{{ block:member_signatures }}`
- `{{ block:shareholder_addresses }}`
- `{{ block:acknowledgement_signatures }}`
- `{{ block:attendance_signatures }}`

Block markers must remain as the only text in their paragraph. The renderer
replaces each marker with OOXML tables/paragraphs or removes it. Signature,
address, and acknowledgment blocks use two people per row, continue in new rows
after four people, and leave the right cell blank for an odd final person.
Section 90 is the sole exception for `attendance_signatures`: it renders a
bordered two-column `NAME`/`SIGNATURE` register with one member per row and a
minimum of ten body rows. Templates 1/2 and all other signature blocks keep
their existing two-person layout.

Resolution-heading paragraphs use a 0.5-inch hanging indent and justified
alignment. A heading that wraps therefore continues beneath the heading text,
not beneath its resolution number, while its first line follows the reference
document's evenly spaced alignment.

## Fidelity and release gates

A production output must:

1. Open as a valid DOCX package.
2. Contain no unresolved `{{ ... }}` markers or source annotations.
3. Templates 1/2 contain the DWR Authority to File resolution. Template 3
   follows the Section 90 reference resolution set and intentionally omits it.
4. Use the FS approval date for the board signatures and FS circulation date for
   member signatures and the letter.
5. Use the statutory declarant, without substituting another director.
6. Preserve the fixed registered-office address and two-column people layout.
7. Have no unintended trailing blank page, clipping, or overlapping content in
   the Word-rendered output.
8. Reject a missing or invalid FS financial-year start date and a start date
   later than the financial-year end date.

When changing the template, rebuild representative zero-fee and positive-fee
documents, export them through Microsoft Word, and inspect every rendered page.
