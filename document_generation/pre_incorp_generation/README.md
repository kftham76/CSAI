# Pre-Incorporation Director Document Generator

This package produces two retained-template DOCX files for every current
director. It reads the Excel-mirrored `new_incorp.db:New_Incorp` table
through the `csai_langchain` repository layer and never writes corrections
back to the database or modifies the retained templates.

## Interactive command

```powershell
python -m document_generation.pre_incorp_generation `
  --company "HOSAY 3 BAKERY SDN. BHD." `
  --overwrite
```

The program retrieves data before prompting and shows the detected company,
incorporation date, current-director count, names, IDs, shares, sources, and
missing fields. It does not ask the user to confirm or edit the director roster
and does not prompt for director information. The only interactive input is a
missing Reference No.; incomplete database data blocks generation.

Options:

- `--reference-no VALUE`: prefill the Reference No.
- `--output-dir PATH`: override `D:\CSAI_DATA\pre-incorp Output`.
- `--overwrite`: transactionally replace colliding generated files.
- `--dry-run`: retrieve and report the draft without prompting or writing files.

A normal run from a non-interactive terminal returns `input_required` instead
of waiting for input.

## Retrieval order

- Director roster, director information, and shares: the current `DirectorN`
  and matching `MemberN` columns from the matched
  `new_incorp.db:New_Incorp` row.
- Company details and incorporation date: the company columns from that same
  row, with `S14 Incorporation Date` used only when `Incorporate Date` is blank.
- Matching DOB, nationality, race, residential address, email, and phone:
  the closest matching `BO1` through `BO4` column group from that same row, matched by
  director identification number wherever possible.
- Manual terminal input: highest priority for the current run only.

EBOS Business Address and Designation remain suggestions only for missing
Service Address and Business Occupation. They are never silently substituted.
The Excel workbook is not opened during document generation, and no other
information database is queried by this package.

## Python API

```python
from document_generation import (
    generate_pre_incorp_documents,
    prepare_pre_incorp_generation,
)

prepared = prepare_pre_incorp_generation("HOSAY 3 BAKERY SDN. BHD.")
draft = prepared.draft

# Generate from the retrieved current-director draft.
result = generate_pre_incorp_documents(
    "HOSAY 3 BAKERY SDN. BHD.",
    reference_no="2024B068109",
    draft=draft,
    confirmed=True,
)
```

Each draft field includes its value, source, source date, candidates, and one of
these statuses: `detected`, `missing`, `conflicting`, `provisional`, or
`user-supplied`.

All current directors are validated before any output is written. The Notice signature
date and unsupported disclosure areas remain blank. The S201 declaration date
is one day before the confirmed incorporation date.
