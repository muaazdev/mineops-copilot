# ADR-0002: Hybrid retrieval with app-side RRF over OpenSearch (BM25) + Qdrant (dense)

- Status: Accepted
- Date: 2026-10-20

## Context
The JD names OpenSearch and Qdrant explicitly. Both engines can do hybrid on their own (OpenSearch hybrid query + normalization processor; Qdrant sparse+dense with fusion). We need a fair, measurable comparison of BM25 / dense / hybrid / hybrid+rerank, and support for Arabic.

## Decision
Query both engines in parallel with identical metadata filters, fuse in the application with Reciprocal Rank Fusion (k=60, configurable), then rerank the top-N with a multilingual cross-encoder. Weighted score fusion (min-max normalized) is implemented as an alternative for the eval only.

## Alternatives considered
- OpenSearch-native hybrid (BM25 + k-NN in one cluster) — one system to run, but couples us to one engine and makes Qdrant redundant.
- Qdrant-native sparse+dense — strong option; loses OpenSearch's mature language analyzers (Arabic stemming/normalization) and the JD's OpenSearch requirement.
- Weighted fusion as default — needs score normalization and per-corpus tuning; RRF is rank-based and robust without tuning.

## Consequences
- Two round-trips per query (parallelized); filter logic must be expressed twice and kept in sync (single filter model → two translators, tested).
- Engine-agnostic fusion makes the eval honest and swapping engines cheap.

## Revisit when
Latency budget is dominated by the double query, or eval shows native hybrid beating app-side RRF.
