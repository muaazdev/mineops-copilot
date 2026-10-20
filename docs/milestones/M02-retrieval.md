# M2 — Bilingual corpus, ingestion, hybrid retrieval, rerank, eval

**Goal:** `make ingest && make eval-retrieval` produces a committed results table comparing BM25 / dense / hybrid / hybrid+rerank, overall and per language.

**Cost:** none (CPU models). Model downloads are a few GB — warn the owner before first download.

**Owner is weaker in OpenSearch — explain mapping/analyzer/query choices in comments and in `docs/interview/M02.md`.**

## Tasks
1. **Corpus generator** (`packages/mineops-data` or a `corpus` module): 60–100 markdown docs with frontmatter per SPEC §5. Template-driven with structured sections (Purpose, Scope, PPE, Steps, Hazards, References). ≥25% Arabic-authored; ~10 topics in both languages; ~8 documents with a superseding newer version. Deterministic. Optional: render ~10 to PDF for PDF-ingestion path.
2. **Chunker**: heading-aware markdown splitter, ~400–600 tokens, overlap ~60, carries `doc_id, section_path, chunk_idx` + all frontmatter; `is_latest` computed.
3. **Filter model**: one Pydantic `RetrievalFilter` (site, asset_type, doc_type, lang, as_of, latest_only) with two translators → OpenSearch bool filter and Qdrant `Filter`. Property-test that both translators agree on a fixture set.
4. **OpenSearch**: index template, `text` field with subfields `text.en` (english analyzer) and `text.ar` (arabic analyzer), plus `title` boosted; keyword fields for filters; `effective_date` as date. Query by detected language; fallback `multi_match` across both. Explain BM25 params (k1, b) and why defaults are kept.
5. **Qdrant**: collection with cosine distance, payload indexes on filter fields, embedder = multilingual BGE-M3-class model (pin exact model + revision). Batch upsert with stable point IDs.
6. **Fusion**: RRF (k configurable) and weighted (min-max normalized) fusion functions, pure and unit-tested.
7. **Reranker**: multilingual cross-encoder (pin), top-N in → top-K out, batched.
8. **`HybridRetriever`** API: `search(query, filter, mode=bm25|dense|hybrid|hybrid_rerank, k)` returning chunks with scores per stage (for explainability and eval).
9. **Eval set** `data/eval/queries.jsonl` (~60 queries: ~35 EN, ~20 AR, ~5 cross-lingual) + `qrels.jsonl` with graded relevance (0–2). Include filter-dependent queries and superseded-version traps.
10. **Eval harness** `eval/retrieval_eval.py`: recall@5/10, MRR@10, nDCG@10, p50/p95 latency, per mode and per language; writes `eval/results/retrieval.md` + JSON.
11. Integration tests with testcontainers OpenSearch + Qdrant on a tiny corpus.

## Done checklist
- [ ] `make ingest`, `make eval-retrieval` work from clean clone (after `make up-all`)
- [ ] Results table committed; short analysis paragraph (where hybrid wins, where rerank helps, Arabic results)
- [ ] `docs/interview/M02.md` (RRF vs weighted, OpenSearch vs Qdrant hybrid, Arabic analyzers, chunking, eval metrics; sovereign note)
