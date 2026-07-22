# Structured Entity Vector Records for RAG

**Version:** 1.0  
**Date:** 2026-07-21  
**Status:** Approved

## Problem

RAG pipeline returns incomplete entity-specific results. "List companies where Khor Yea Jye is a member" returns 4 of 6. Root cause: noisy concatenated payloads where entity names are buried among 40+ fields, and Client_Master records lack separate `name`/`role` payload fields.

## Solution

Restructure `build_vectors.py` to emit one Qdrant point per logical entity instead of one per JSON row. Then simplify `rag_chain.py` to use Qdrant payload filters directly.

### Vector Record Types

**Company Profile** (1 per Client_Master row):
- `text`: Company registration info only
- `name`: "" (empty)
- `role`: "company"
- `company`: Company Name
- `source`: "Client_Master"

**Director Record** (1 per director per Client_Master row):
- `text`: "Name: KHOR YEA JYE | Designation: Director | Company: XX | IC: ... | Nationality: ..."
- `name`: Director's name
- `role`: "director"
- `company`: Company Name
- `ic`: IC number
- `source`: "Client_Master"

**Member Record** (1 per member per Client_Master row):
- `text`: "Name: KHOR YEA JYE | Role: Member | Company: XX | Shares: 50 | IC: ..."
- `name`: Member's name
- `role`: "member"
- `company`: Company Name
- `ic`: IC number
- `source`: "Client_Master"

**BO Record** (1 per EBOS_Master row, unchanged except new `role` field):
- `text`: Existing EBOS text
- `name`: Person name (existing)
- `role`: "director" (new)
- `company`: Company Name (existing)
- `designation`: Designation (existing)
- `source`: "EBOS_Master"

### Query Logic (rag_chain.py)

Simple filter-based query replaces the current complex merge:

```
if entity_name detected:
    filters = []
    if entity_name: add name filter
    if role detected in question: add role filter
    query_points(query=vector, query_filter=Filter(must=filters), limit=15)
else:
    query_points(query=vector, limit=10)
```

### Files Changed

- `build_vectors.py` — Major rewrite
- `rag_chain.py` — Simplify query section
- Qdrant storage — delete and rebuild
