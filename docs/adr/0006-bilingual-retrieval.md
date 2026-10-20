# ADR-0006: Bilingual (Arabic + English) retrieval

- Status: Accepted
- Date: 2026-10-20

## Context
Target users are in Saudi Arabia; SOPs and questions may be Arabic, English, or mixed. Arabic has rich morphology, optional diacritics, letter variants (أ/إ/آ/ا, ى/ي, ة/ه) that break naive keyword search.

## Decision
- Documents carry `lang`. OpenSearch mapping uses language subfields with built-in `arabic` (normalization + light stemming) and `english` analyzers; queries are routed by detected language with a multi-match fallback.
- Dense retrieval uses a multilingual embedder (BGE-M3 class) so Arabic queries can retrieve English docs and vice versa.
- Reranker is a multilingual cross-encoder.
- Eval set includes Arabic and cross-lingual queries; metrics are reported per language.
- The answer language follows the user.

## Alternatives considered
- Translate everything to English at ingest — loses fidelity and adds a translation dependency.
- English-only embedder — fails cross-lingual and Arabic recall.

## Consequences
- Heavier embedder on CPU (slower ingest); acceptable at corpus size.
- Need Arabic-authored synthetic documents of decent quality.

## Revisit when
Corpus grows enough that CPU embedding is the bottleneck.
