# CSAI Document Generation

The document-generation codebase contains two independent programs. Both read
the existing `csai_langchain` repositories in read-only mode.

## AGM

```powershell
python -m document_generation.agm_generation --company "CS SURIA SDN. BHD." --overwrite
```

The legacy command remains an AGM-compatible alias:

```powershell
python -m document_generation --company "CS SURIA SDN. BHD." --overwrite
```

AGM implementation details are documented in
`document_generation\agm_generation\README.md`. Its templates are under
`document_generation\templates\agm`.

## Pre-incorporation

```powershell
python -m document_generation.pre_incorp_generation `
  --company "EXAMPLE SDN. BHD." `
  --overwrite
```

The program retrieves the current director/member roster and supporting
company and EBOS/BO fields through `csai_langchain` from the Excel-mirrored
`new_incorp.db:New_Incorp` table. It does not request director confirmation or
manual director fields; the only interactive input is a missing Reference No.
Each current director receives one S201 declaration and one Director's Notice
under Sections 57, 219 and 221.

The default output is
`D:\CSAI_DATA\pre-incorp Output\<Company Name>`. Use `--dry-run` to retrieve a
source-attributed draft without prompting or creating DOCX files.

## Tests

```powershell
python -m unittest discover -s document_generation\tests -v
```
