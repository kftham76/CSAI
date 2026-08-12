# Pre-Incorporation Marker Template Contract

The two DOCX files under `document_generation\templates\pre-incorp` are the
production design authorities. They intentionally contain literal AGM-style
`{{ ... }}` markers. Normal generation copies a production template and patches
only `word/document.xml`; every other package part is copied byte-for-byte.

The sample-filled source files that existed before marker conversion are kept
under `document_generation\templates\pre-incorp\originals-before-marker-conversion`.
The conversion utility verifies those original hashes and never overwrites an
existing backup.

## S201 and declaration

- Production file: `Pre incorp. S201 and declaration Hosay 3 Bakery-THK.docx`
- Production SHA-256: `6b73455b1de211c804c8ffa27158f24cdf51658ffca7fd654a8c005307f086f7`
- Original SHA-256: `98ffb593cc0341e85fdf94c06a3175aee92c7123a639f7ba86d4ad7d1d60989e`
- Structure: one A4 portrait section and three tables.
- Marker inventory (the number in parentheses is the required occurrence
  count):
  - `{{ reference_no }}` (1)
  - `{{ company_name }}` (4)
  - `{{ director_name }}` (2)
  - `{{ identification_label }}` (2)
  - `{{ director_id }}` (2)
  - `{{ declaration_date }}` (2)
  - `{{ residential_address_line_1 }}` (1)
  - `{{ residential_address_line_2 }}` (1)
  - `{{ service_address_line_1 }}` (1)
  - `{{ service_address_line_2 }}` (1)
  - `{{ business_occupation }}` (1)
  - `{{ email }}` (1)
  - `{{ phone }}` (1)

The signature block is exactly:

```text
Name: {{ director_name }}
{{ identification_label }}: {{ director_id }}
Date of Declaration: {{ declaration_date }}
```

The former `(director)` and `(director ic)` drafting annotations are not part
of the production template.

Residential and service addresses use two dedicated rows. The first marker
follows the colon; the continuation paragraph has a 180-twip left indent. All
four marker runs are explicitly black at the template's normal 12 pt size.
Rendering balances each address at word boundaries. Both lines change to 10.5
pt when either line exceeds 44 characters, and an address is rejected when it
cannot fit within two 60-character compact lines.

## Director's Notice

- Production file: `pre_incorp_Director's_Notice_under_S57,_S219_&_S221.(Hosay 3 Bakery) THK.docx`
- Production SHA-256: `51a500c96c451e5a12ed4cd5cf869c212ccb86bbc8f25b5cc17f73c34f7ec688`
- Original SHA-256: `4f855fe3b840c8f4298a2c0a7fbe3c674bb0977f9028c4a787f80c24fd4efcf2`
- Structure: two sections, three tables, portrait opening pages, and an
  odd-page landscape shareholding section.
- Marker inventory:
  - `{{ company_name }}` (2)
  - `{{ director_name }}` (3)
  - `{{ director_identification }}` (1)
  - `{{ date_of_birth }}` (1)
  - `{{ nationality_and_race }}` (1)
  - `{{ residential_address_line_1 }}` (1)
  - `{{ residential_address_line_2 }}` (1)
  - `{{ residential_address_line_3 }}` (1)
  - `{{ service_address }}` (1)
  - `{{ business_occupation }}` (1)
  - `{{ email }}` (1)
  - `{{ shares_fully_owned }}` (1)

`{{ director_identification }}` includes the Notice's required type code:
`(B)`, `(P)`, `(R)`, `(Z)`, or `(M)`.

Former name, outside public-company directorships, corporation interests,
acquisition/cessation transactions, and the Notice signature date remain
intentionally blank or retain their original static dash.

## Fidelity gates

- The renderer validates the complete marker inventory before replacing any
  marker. A missing, duplicated, unexpected, or unresolved marker blocks the
  document.
- Renderer replacement-map keys must exactly equal the corresponding marker
  inventory.
- Sample Hosay/Tan/reference values and helper annotations must not appear in
  either production template or generated output.
- Package-part names and every part outside `word/document.xml` must match the
  original template. Section properties, table properties and grids, row
  properties, and cell geometry must remain unchanged.
- Static legal text and the fixed company-secretary address must not be
  rewritten.
- `python -m document_generation.pre_incorp_generation.audit_marker_templates`
  performs the structural contract audit without generating documents.

Visual pagination and Word rendering were intentionally not performed for the
marker-conversion change because the requested verification scope was code and
OOXML structure only.
