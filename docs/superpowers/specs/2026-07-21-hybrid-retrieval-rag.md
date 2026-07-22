# Hybrid Two-Stage Retrieval for RAG

**Version:** 1.0  
**Date:** 2026-07-21  
**Status:** Draft

## Problem

The RAG pipeline (`rag_chain.py`) returns incomplete results for entity-specific queries. Example: "list companies where khor yea jye is being appointed as director" returns 1-2 companies instead of the 6 that exist in the data.

## Root Cause

Three compounding issues:

1. **`limit=5`** — Too few documents retrieved. With 377 total docs and 6 mentioning "KHOR YEA JYE", top 5 may not cover all.
2. **Noisy text payloads** — `build_vectors.py` concatenates all k:v fields into one blob. Entity names like "KHOR YEA JYE" get diluted among 20+ fields, lowering embedding similarity scores.
3. **No exact-name fallback** — Pure vector search has no mechanism to catch exact entity matches that score just below the cutoff.

## Solution: Two-Stage Retrieval + Smart Merge

### Stage 1: Vector Search (limit=30)

- Increase `limit` from 5 → 30
- Catches semantically relevant documents broadly
- With 30 slots, all 6 relevant documents have high probability of inclusion

### Stage 2: Entity-Aware Filter Query

- Extract potential entity names from question using heuristics:
  - ALL CAPS sequences (e.g., "KHOR YEA JYE" → exact match)
  - Multi-word tokens after "who", "where", "for", "by", "of", "about", "does", "is", "are"
- Extracted name is uppercased to match DB format (all names stored in ALL CAPS)
- If entity detected, run second Qdrant query with payload filter on `name` field
- Uses Qdrant `Filter` + `Match(value=ENTITY_NAME)` on existing payload fields (`name`, `company`)
- **Limitation:** if query uses varied casing (e.g., "Khor Yea Jye") without ALL CAPS, heuristic may not trigger. The user should use ALL CAPS or exact name format for entity lookup queries.
- If no entity detected, skip Stage 2 (pure vector search)

### Stage 3: Merge + Deduplicate

- Combine results from Stage 1 + Stage 2
- Deduplicate by `company` payload field (keep highest score per company)
- Sort by score descending
- Limit final context to top 15 unique companies

### Stage 4: Prompt Update

- Add instruction: "List ALL relevant entries from the context. Do not omit any matching items."

## Files Changed

- `C:\CSAI_OS\06_LangChain\Retrieval\rag_chain.py` — only file modified

## Test Cases

| Query | Expected Behavior |
|-------|------------------|
| "list companies where KHOR YEA JYE is director" | Returns all 6 companies |
| "what is annual return process?" | Vector search only, general answer |
| "tell me about FERRECO SDN BHD" | Vector search catches by company name in text |
| "who are the directors of easy commitment?" | Vector search + name filter merge |
| "how many companies have foreign ownership?" | Vector search only |

## Future Considerations

- Full-text index on `text` payload for `MatchText` filtering
- Sparse vector support for native Qdrant hybrid search
- Cleaner payload structure (separate points per director/company)
