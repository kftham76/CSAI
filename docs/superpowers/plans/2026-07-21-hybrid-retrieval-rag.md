# Hybrid Retrieval for RAG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix RAG pipeline to return complete results for entity-specific queries by implementing two-stage retrieval with deduplication.

**Architecture:** Add entity-aware filtered query alongside vector search, merge results, deduplicate by company, update prompt.

**Tech Stack:** Python, Qdrant, SentenceTransformers, re (stdlib)

## Global Constraints

- Only modify `C:\CSAI_OS\06_LangChain\Retrieval\rag_chain.py`
- No new dependencies
- Names in Qdrant payloads are ALL CAPS format
- Python environment at `C:\CSAI_OS\.venv`

---

### Task 1: Rewrite retrieval section in rag_chain.py

**Files:**
- Modify: `C:\CSAI_OS\06_LangChain\Retrieval\rag_chain.py` (lines 27-59)

**Interfaces:**
- Consumes: Qdrant client, SentenceTransformer model, user `question` string
- Produces: `context` string with deduplicated, ranked company data for LLM prompt

- [ ] **Step 1: Read current rag_chain.py**

Run: `type "C:\CSAI_OS\06_LangChain\Retrieval\rag_chain.py"`

Understand current structure before editing.

- [ ] **Step 2: Replace the query section (lines 27-45)**

Replace current single query with two-stage retrieval.

Old code (lines 27-45):
```python
    results = client.query_points(
        collection_name="csai_master",
        query=vector,
        limit=5
    ).points

    context = ""

    for r in results:

        context += (
            r.payload["text"]
            + "\n\n"
        )
```

New code:
```python
    import re
    from qdrant_client.models import Filter, FieldCondition, Match

    # Stage 1: Vector search (limit=30)
    vector_results = client.query_points(
        collection_name="csai_master",
        query=vector,
        limit=30
    ).points

    # Stage 2: Entity-aware filter query
    filter_points = []
    upper_words = re.findall(r'\b[A-Z]{2,}\b', question)
    entity_name = " ".join(upper_words) if upper_words else ""

    if entity_name:
        try:
            filter_results = client.query_points(
                collection_name="csai_master",
                query=vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="name",
                            match=Match(value=entity_name)
                        )
                    ]
                ),
                limit=30
            ).points
            filter_points = filter_results
        except Exception:
            filter_points = []

    # Stage 3: Merge + deduplicate by company
    seen_companies = set()
    merged = []

    for r in vector_results + filter_points:
        company = r.payload.get("company", "")
        if company and company not in seen_companies:
            seen_companies.add(company)
            merged.append(r)
        elif not company and r.id not in seen_companies:
            seen_companies.add(r.id)
            merged.append(r)

    # Prepare context from top 15 unique results
    context = ""
    for r in merged[:15]:
        context += r.payload["text"] + "\n\n"
```

- [ ] **Step 3: Update the system prompt**

Old prompt (lines 47-59):
```python
    prompt = f"""
You are a Malaysian Company Secretary AI Assistant.

Answer ONLY using the information below.

Context:
{context}

Question:
{question}

Answer:
"""
```

New prompt:
```python
    prompt = f"""
You are a Malaysian Company Secretary AI Assistant.

Answer ONLY using the information below.

List ALL relevant entries from the context. Do not omit any matching items.

If multiple companies or persons match the question, list them all.

Context:
{context}

Question:
{question}

Answer:
"""
```

- [ ] **Step 4: Add import at top of file**

Add to line 3 (after existing imports):
```python
import re
from qdrant_client.models import Filter, FieldCondition, Match
```

- [ ] **Step 5: Verify by running**

Run with a test query:
```bash
echo "list companies where KHOR YEA JYE is being appointed as director" | & "C:\CSAI_OS\.venv\Scripts\python.exe" "C:\CSAI_OS\06_LangChain\Retrieval\rag_chain.py"
```

Expected: Returns more than 2 companies (should list all 6).

- [ ] **Step 6: Verify general query still works**

```bash
echo "what is the annual return process?" | & "C:\CSAI_OS\.venv\Scripts\python.exe" "C:\CSAI_OS\06_LangChain\Retrieval\rag_chain.py"
```

Expected: Returns a coherent answer without errors.
