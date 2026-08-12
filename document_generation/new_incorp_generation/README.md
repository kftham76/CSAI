# New-incorporation document generator

This package is isolated from the AGM and pre-incorporation generators. It reads the existing `New_Incorp` repository in SQLite read-only mode and publishes one atomic company batch. Company identity uses `Company Name` and `Reg No`; incorporation details use `S14 Incorporation Date`, `S14 Registered Address`, and `S14 Business Address`; people and shares use the current numbered `DirectorN` and `MemberN` fields from the vertical Excel/SQLite schema.

```powershell
python -m document_generation.new_incorp_generation --company "HOSAY 3 BAKERY SDN. BHD." --dry-run
python -m document_generation.new_incorp_generation --company "HOSAY 3 BAKERY SDN. BHD."
python -m document_generation.new_incorp_generation --company "HOSAY 3 BAKERY SDN. BHD." --overwrite
```

The default output root is `D:\CSAI_DATA\new-incorp-output`. Use `--output-dir PATH` to override it. A collision blocks the complete batch unless `--overwrite` is supplied.

Programmatic APIs:

```python
from document_generation.new_incorp_generation import (
    generate_new_incorp_documents,
    prepare_new_incorp_generation,
)
```

`prepare_new_incorp_generation()` returns the validated context, status, issues, preview, and expected document count. `generate_new_incorp_documents()` additionally returns all output paths and publishes only after every staged DOCX passes validation.

Run the template fidelity audit with:

```powershell
python -m document_generation.new_incorp_generation.audit_templates
```
