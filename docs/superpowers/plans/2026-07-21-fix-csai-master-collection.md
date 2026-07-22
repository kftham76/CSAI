# Fix csai_master Collection Not Found — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run existing pipeline to populate Qdrant with vector embeddings so `rag_chain.py` works.

**Architecture:** Two-step data pipeline: SQLite → JSON (export) → Qdrant vectors (build), then RAG queries work.

**Tech Stack:** Python, Qdrant, SentenceTransformers, SQLite

## Global Constraints

- Paths must use `06_LangChain` (underscore), not `06 LangChain` (space)
- All scripts run from project root `C:\CSAI_OS`
- Python commands use `.venv` environment at `C:\CSAI_OS\.venv`
- No new dependencies — use existing installed packages

---

### Task 1: Fix paths in export and build scripts

**Files:**
- Modify: `C:\CSAI_OS\06_LangChain\Export\sqlite_to_json.py:9`
- Modify: `C:\CSAI_OS\06_LangChain\Embeddings\build_vectors.py:20`

Both reference `06 LangChain` (space). Actual directory is `06_LangChain` (underscore).

- [ ] **Step 1: Fix sqlite_to_json.py line 9**

Change `ROOT / "06 LangChain" / "data_json"` → `ROOT / "06_LangChain" / "data_json"`

- [ ] **Step 2: Fix build_vectors.py line 20**

Change `r"C:\CSAI_OS\06 LangChain\data_json"` → `r"C:\CSAI_OS\06_LangChain\data_json"`

---

### Task 2: Export SQLite DBs to JSON

**Files:**
- Run: `C:\CSAI_OS\06_LangChain\Export\sqlite_to_json.py`

- [ ] **Step 1: Export databases**

Run: `python "C:\CSAI_OS\06_LangChain\Export\sqlite_to_json.py"`

Expected: Creates `C:\CSAI_OS\06_LangChain\data_json\csai_master\*.json` and `...\ebos_master\*.json`

---

### Task 3: Build Qdrant vector collection

**Files:**
- Run: `C:\CSAI_OS\06_LangChain\Embeddings\build_vectors.py`

- [ ] **Step 1: Build vectors**

Run: `python "C:\CSAI_OS\06_LangChain\Embeddings\build_vectors.py"`

Expected: Creates `csai_master` collection in Qdrant storage, inserts vector points

---

### Task 4: Verify

- [ ] **Step 1: Run rag_chain.py**

Run: `python "C:\CSAI_OS\06_LangChain\Retrieval\rag_chain.py"`

Expected: No `Collection not found` error. Prompt accepts questions and returns Company Secretary AI answers.
