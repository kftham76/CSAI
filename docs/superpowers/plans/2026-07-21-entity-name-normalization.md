# Entity Name Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize entity names (auditor, company, person) at write-time and query-time so formatting variations (whitespace, initial spacing, trailing junk) don't cause missed matches.

**Architecture:** Single `normalizer.py` module called by both `build_vectors.py` (stores `_std` fields in Qdrant payload) and `metadata_search.py`/`router.py` (normalizes queries before matching). Raw values preserved for display.

**Tech Stack:** Python 3.12+, Qdrant (local mode), re (stdlib)

## Global Constraints

- Raw entity values must be preserved in `company`, `name`, `text` fields for display
- Normalized values stored in `company_std`, `name_std`, `auditor_std` sibling fields
- All Qdrant `MatchValue` filters must use `_std` fields
- Normalization must be deterministic (same input → same output)
- Must not merge different entities (conservative rules only)
- Qdrant collection must be rebuilt after changes

---

### Task 1: Create `normalizer.py`

**Files:**
- Create: `06_LangChain/Retrieval/normalizer.py`
- Test: (tested via Task 5 integration)

**Interfaces:**
- Produces: `normalize_name(raw: str) -> str`, `normalize_match(raw: str) -> str`

- [ ] **Step 1: Write `normalizer.py`**

Content of `06_LangChain/Retrieval/normalizer.py`:

```python
import re


def normalize_name(raw: str) -> str:
    """Normalize entity name for exact-match dedup/storage."""
    if not raw:
        return ""
    s = raw.strip()
    s = s.upper()
    s = re.sub(r'\s+', ' ', s)  # collapse whitespace
    # Normalize initial spacing: "Y. H. CHANG" → "Y.H.CHANG"
    s = re.sub(r'(?<=\b\w\.)\s+(?=\w\.)', '', s)
    s = re.sub(r'(?<=\b\w\.)\s+(?=\w\b)', '', s)
    # Standardize company suffixes
    s = re.sub(r'\bSDN\.?\s*BHD\.?\b', 'SDN BHD', s)
    s = re.sub(r'\bS/B\b', 'SDN BHD', s)
    s = re.sub(r'\bNO\.?\b', 'NO', s)
    s = re.sub(r'\bLOT\.?\b', 'LOT', s)
    # Strip trailing noise
    s = re.sub(r'\s+N$', '', s)
    s = re.sub(r'\s+S/B$', '', s)
    return s.strip()


def normalize_match(raw: str) -> str:
    """Normalize search query — same rules as normalize_name."""
    return normalize_name(raw)
```

- [ ] **Step 2: Verify import works**

Run: `C:\CSAI_OS\.venv\Scripts\python.exe -c "from normalizer import normalize_name, normalize_match; print('OK')"` with working dir `C:\CSAI_OS\06_LangChain\Retrieval`
Expected: `OK`

- [ ] **Step 3: Test known cases**

Run:
```python
from normalizer import normalize_name
assert normalize_name("") == ""
assert normalize_name("  Y.H.CHANG  &  PARTNERS  ") == "Y.H.CHANG & PARTNERS"
assert normalize_name("Y. H. CHANG & PARTNERS") == "Y.H.CHANG & PARTNERS"
assert normalize_name("Y.H. CHANG & PARTNERS") == "Y.H.CHANG & PARTNERS"
assert normalize_name("Y.H.CHANG & PARTNERS N") == "Y.H.CHANG & PARTNERS"
assert normalize_name("ABC SDN. BHD.") == "ABC SDN BHD"
assert normalize_name("ABC S/B") == "ABC SDN BHD"
print("ALL OK")
```

Expected: `ALL OK`

- [ ] **Step 4: Commit**

```bash
git add 06_LangChain/Retrieval/normalizer.py
git commit -m "feat: add entity name normalizer"
```

---

### Task 2: Update `build_vectors.py` — add `_std` fields

**Files:**
- Modify: `06_LangChain/Embeddings/build_vectors.py`
- Re-index: will run in Task 4

**Interfaces:**
- Consumes: `normalize_name()` from Task 1
- Produces: Qdrant points with `company_std`, `name_std`, `auditor_std` fields

- [ ] **Step 1: Add import at top of build_vectors.py**

After line 7 (`from qdrant_client.models import ...`), add:
```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Retrieval"))
from normalizer import normalize_name
```

- [ ] **Step 2: Update company profile point (lines 68-75)**

Change from:
```python
add_point(comp_text, {
    "text": comp_text,
    "company": company,
    "name": "",
    "role": "company",
    "ic": "",
    "source": source
})
```

To:
```python
auditor_name = str(row.get("Auditor Name", "") or "")
add_point(comp_text, {
    "text": comp_text,
    "company": company,
    "company_std": normalize_name(company),
    "name": "",
    "role": "company",
    "ic": "",
    "auditor": auditor_name,
    "auditor_std": normalize_name(auditor_name),
    "source": source
})
```

- [ ] **Step 3: Update director record payload (lines 93-101)**

Change from:
```python
add_point(dir_text, {
    "text": dir_text,
    "company": company,
    "name": dir_name,
    "role": "director",
    "designation": "DIRECTOR",
    "ic": dir_ic,
    "source": source
})
```

To:
```python
add_point(dir_text, {
    "text": dir_text,
    "company": company,
    "company_std": normalize_name(company),
    "name": dir_name,
    "name_std": normalize_name(dir_name),
    "role": "director",
    "designation": "DIRECTOR",
    "ic": dir_ic,
    "source": source
})
```

- [ ] **Step 4: Update member record payload (lines 119-127)**

Change from:
```python
add_point(mem_text, {
    "text": mem_text,
    "company": company,
    "name": mem_name,
    "role": "member",
    "designation": "SHAREHOLDER",
    "ic": mem_ic,
    "source": source
})
```

To:
```python
add_point(mem_text, {
    "text": mem_text,
    "company": company,
    "company_std": normalize_name(company),
    "name": mem_name,
    "name_std": normalize_name(mem_name),
    "role": "member",
    "designation": "SHAREHOLDER",
    "ic": mem_ic,
    "source": source
})
```

- [ ] **Step 5: Update EBOS record payload (lines 148-160)**

Change from:
```python
add_point(text, {
    "text": text,
    "company": company,
    "name": name,
    "role": role,
    "ic": ic,
    "designation": designation,
    "bo_type": bo_type,
    "nationality": nationality,
    "category": category,
    "client": client_name,
    "source": source
})
```

To:
```python
add_point(text, {
    "text": text,
    "company": company,
    "company_std": normalize_name(company),
    "name": name,
    "name_std": normalize_name(name),
    "role": role,
    "ic": ic,
    "designation": designation,
    "bo_type": bo_type,
    "nationality": nationality,
    "category": category,
    "client": client_name,
    "source": source
})
```

- [ ] **Step 6: Commit**

```bash
git add 06_LangChain/Embeddings/build_vectors.py
git commit -m "feat: store normalized entity names in _std fields"
```

---

### Task 3: Update `metadata_search.py` — search against `_std` fields

**Files:**
- Modify: `06_LangChain/Retrieval/metadata_search.py`

**Interfaces:**
- Consumes: `normalize_match()` from Task 1
- Changes: All `MatchValue` filters use `_std` fields with normalized query values

- [ ] **Step 1: Add import**

At top of `metadata_search.py`, after line 6 (`from qdrant_client.models import ...`), add:
```python
from normalizer import normalize_match
```

- [ ] **Step 2: Update `search_company` (lines 18-35)**

Change `key="company"` to `key="company_std"` and value to `normalize_match(company)`.

From:
```python
def search_company(company):
    results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="company",
                    match=MatchValue(
                        value=company
                    )
                )
            ]
        ),
        limit=100
    )
    return results[0]
```

To:
```python
def search_company(company):
    results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="company_std",
                    match=MatchValue(
                        value=normalize_match(company)
                    )
                )
            ]
        ),
        limit=100
    )
    return results[0]
```

- [ ] **Step 3: Update `search_directors` (lines 37-63)**

Change `key="company"` → `key="company_std"` and `company` → `normalize_match(company)`.

```python
def search_directors(company):
    results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="company_std",
                    match=MatchValue(
                        value=normalize_match(company)
                    )
                ),
                FieldCondition(
                    key="designation",
                    match=MatchValue(
                        value="DIRECTOR"
                    )
                )
            ]
        ),
        limit=100
    )
    return results[0]
```

- [ ] **Step 4: Update `search_shareholders` (lines 65-91)**

```python
def search_shareholders(company):
    results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="company_std",
                    match=MatchValue(
                        value=normalize_match(company)
                    )
                ),
                FieldCondition(
                    key="designation",
                    match=MatchValue(
                        value="SHAREHOLDER"
                    )
                )
            ]
        ),
        limit=100
    )
    return results[0]
```

- [ ] **Step 5: Update `search_person` (lines 93-112)**

Change `key="name"` → `key="name_std"` and `person` → `normalize_match(person)`.

```python
def search_person(person):
    results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="name_std",
                    match=MatchValue(
                        value=normalize_match(person)
                    )
                )
            ]
        ),
        limit=100
    )
    return results[0]
```

- [ ] **Step 6: Update `search_person_role` (lines 114-160)**

Change `key="name"` → `key="name_std"` and `person` → `normalize_match(person)`.

```python
def search_person_role(
        person,
        role
):

    from qdrant_client.models import (
        Filter as NestedFilter
    )

    results = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[

                FieldCondition(
                    key="name_std",
                    match=MatchValue(
                        value=normalize_match(person)
                    )
                ),

                NestedFilter(
                    should=[

                        FieldCondition(
                            key="designation",
                            match=MatchValue(
                                value=role
                            )
                        ),

                        FieldCondition(
                            key="role",
                            match=MatchValue(
                                value=role.lower()
                            )
                        )

                    ]
                )

            ]
        ),
        limit=100
    )

    return results[0]
```

- [ ] **Step 7: Commit**

```bash
git add 06_LangChain/Retrieval/metadata_search.py
git commit -m "feat: search against normalized _std fields"
```

---

### Task 4: Update `router.py` — normalize extracted entity names

**Files:**
- Modify: `06_LangChain/Retrieval/router.py`

**Interfaces:**
- Consumes: `normalize_match()` from Task 1
- Changes: Normalize company and person names extracted by the router before returning

- [ ] **Step 1: Add import to router.py**

At top of `router.py`, after line 1 (`import json`), add:
```python
from normalizer import normalize_match
```

- [ ] **Step 2: Update the return values in `route()` (lines 136-154)**

Current code returns raw extracted values from the LLM. Normalize them:

Change from:
```python
    try:

        response = router_llm.invoke(
            prompt
        ).content

        data = json.loads(response)

        return {
            "intent":
                data.get(
                    "intent",
                    "knowledge"
                ),

            "company":
                data.get(
                    "company",
                    ""
                ),

            "person":
                data.get(
                    "person",
                    ""
                )
        }

    except Exception:

        return {
            "intent": "knowledge",
            "company": "",
            "person": ""
        }
```

To:
```python
    try:

        response = router_llm.invoke(
            prompt
        ).content

        data = json.loads(response)

        return {
            "intent":
                data.get(
                    "intent",
                    "knowledge"
                ),

            "company":
                normalize_match(
                    data.get(
                        "company",
                        ""
                    )
                ),

            "person":
                normalize_match(
                    data.get(
                        "person",
                        ""
                    )
                )
        }

    except Exception:

        return {
            "intent": "knowledge",
            "company": "",
            "person": ""
        }
```

- [ ] **Step 3: Commit**

```bash
git add 06_LangChain/Retrieval/router.py
git commit -m "feat: normalize entity names extracted by router"
```

---

### Task 5: Re-index and verify

**Files:**
- Run: `06_LangChain/Embeddings/build_vectors.py`

- [ ] **Step 1: Stop existing Python processes and clean Qdrant**

```bash
Stop-Process -Id (Get-Process python | Where-Object { $_.Id -ne $pid } | Select-Object -ExpandProperty Id) -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Remove-Item "C:\CSAI_OS\07 Qdrant\storage\collection\csai_master" -Recurse -Force -ErrorAction SilentlyContinue
```

- [ ] **Step 2: Run build_vectors.py**

```bash
C:\CSAI_OS\.venv\Scripts\python.exe -m "06_LangChain.Embeddings.build_vectors" 2>&1
```

Expected output: `Total Points: 693` and `VECTOR BUILD DONE`

- [ ] **Step 3: Verify _std fields exist**

```bash
C:\CSAI_OS\.venv\Scripts\python.exe -c @"
from qdrant_client import QdrantClient
c = QdrantClient(path=r'C:\CSAI_OS\07 Qdrant\storage')
r = c.scroll('csai_master', limit=700)
# Check company_std exists
with_std = [p for p in r[0] if p.payload.get('company_std')]
without_std = [p for p in r[0] if not p.payload.get('company_std')]
print(f'With company_std: {len(with_std)}, Without: {len(without_std)}')
# Check name_std
with_namestd = [p for p in r[0] if p.payload.get('name_std')]
print(f'With name_std: {len(with_namestd)}')
# Show sample normalization
for p in with_std[:3]:
    print(f'  raw=[{p.payload.get(\"company\")}]  std=[{p.payload.get(\"company_std\")}]')
"@
```

Expected: `Without: 0` (all points have `company_std`). And for company profile points, `auditor_std` also exists.

- [ ] **Step 4: Verify search returns all 6 companies for KHOR YEA JYE**

```bash
C:\CSAI_OS\.venv\Scripts\python.exe -c @"
import sys; sys.path.insert(0, r'C:\CSAI_OS\06_LangChain\Retrieval')
from qdrant_client import QdrantClient
from metadata_search import init, search_person_role
c = QdrantClient(path=r'C:\CSAI_OS\07 Qdrant\storage'); init(c)
results = search_person_role('KHOR YEA JYE', 'DIRECTOR')
companies = sorted(set(r.payload.get('company') for r in results))
print(f'Director companies: {len(companies)}')
for c in companies: print(f'  {c}')
print()
results2 = search_person_role('KHOR YEA JYE', 'SHAREHOLDER')
companies2 = sorted(set(r.payload.get('company') for r in results2))
print(f'Shareholder companies: {len(companies2)}')
for c in companies2: print(f'  {c}')
"@
```

Expected: 6 companies including `AGENSI SUPREME LOGISTIC SDN. BHD.`

- [ ] **Step 5: Verify normalized search works with variation**

```bash
C:\CSAI_OS\.venv\Scripts\python.exe -c @"
import sys; sys.path.insert(0, r'C:\CSAI_OS\06_LangChain\Retrieval')
from qdrant_client import QdrantClient
from metadata_search import init, search_person_role
c = QdrantClient(path=r'C:\CSAI_OS\07 Qdrant\storage'); init(c)
# Search with lowercase, extra spaces — should still match
results = search_person_role('  khor yea jye  ', 'DIRECTOR')
companies = sorted(set(r.payload.get('company') for r in results))
print(f'Search with bad casing/spaces: {len(companies)} companies')
for c in companies: print(f'  {c}')
"@
```

Expected: Same 6 companies (normalization collapses casing and spaces)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: rebuild vectors with normalized entity fields"
```

---

### Task 6: Update `query_test.py` or create test harness (optional)

If `query_test.py` exists, update it to use normalized search. This is optional — the verification in Task 4 covers correctness.
