# Retrieval eval

63 queries (35 EN, 22 AR, 6 cross-lingual), 117 graded judgements, 65 chunks. Embedder `BAAI/bge-m3@5617a9f`, reranker `BAAI/bge-reranker-v2-m3@953dc6f`, 30 candidates per engine, RRF k=60. Document-level metrics @10. Latency is end-to-end per query on x86_64, 4 CPU, cpu (generated 2026-10-20T21:23:53+00:00).

## Overall

| Mode | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|
| BM25 (OpenSearch) | 0.659 | 0.680 | 0.868 | 0.800 | 11 | 18 |
| Dense (Qdrant) | 0.929 | 0.955 | 0.906 | 0.923 | 141 | 222 |
| Hybrid weighted (min-max 0.5/0.5) | 0.847 | 0.942 | 0.896 | 0.892 | 184 | 261 |
| Hybrid RRF (k=60) | 0.680 | 0.735 | 0.876 | 0.827 | 161 | 210 |
| Hybrid RRF + rerank (30→10) | 0.939 | 0.960 | 0.966 | 0.954 | 30784 | 32043 |

## By query language

| Mode | EN nDCG@10 | EN MRR@10 | AR nDCG@10 | AR MRR@10 | Cross nDCG@10 | Cross MRR@10 |
|---|---|---|---|---|---|---|
| BM25 (OpenSearch) | 0.892 | 0.971 | 0.852 | 0.939 | 0.069 | 0.000 |
| Dense (Qdrant) | 0.955 | 0.952 | 0.951 | 0.947 | 0.631 | 0.486 |
| Hybrid weighted (min-max 0.5/0.5) | 0.953 | 0.986 | 0.933 | 0.955 | 0.385 | 0.157 |
| Hybrid RRF (k=60) | 0.903 | 0.971 | 0.880 | 0.955 | 0.188 | 0.033 |
| Hybrid RRF + rerank (30→10) | 0.966 | 1.000 | 0.971 | 0.977 | 0.822 | 0.727 |

## Version-filter ablation

With `latest_only=False`, mode `hybrid_rerank` ranked a superseded revision first on 4 of 12 version-trap queries (0 with the default filter, by construction).

<!-- analysis: hand-written, preserved by retrieval_eval.py -->
## Analysis

**The reranked hybrid is best on every metric and in every language group.** nDCG@10 is 0.954 against 0.923 for dense alone and 0.800 for BM25. MRR@10 is 0.966, and every English query gets its answer document at rank 1 (MRR 1.000). The cross-encoder pays off most where first-stage ranking is weakest: on cross-lingual queries it lifts nDCG from 0.631 (dense) to 0.822, and MRR from 0.486 to 0.727.

**Plain RRF (k=60) underperforms dense on this corpus** (0.827 vs 0.923). Its recall@5 (0.680) is no better than BM25's. The cause is that **BM25 never abstains**: the cross-language fallback clause always matches common words, so BM25 returns a full candidate list even on cross-lingual queries, where it is essentially noise (nDCG 0.069). RRF uses ranks only, so that noise weighs as much as dense's confident hits. In a 65-chunk corpus most chunks also appear in both candidate lists, so RRF behaves like rank averaging. Shrinking candidate depth from 30 to 20 only moves RRF from 0.827 to 0.844. Min-max weighted fusion keeps dense's score margin and does better (0.892, cross-lingual 0.385 vs 0.188).

**Where BM25 still earns its place.** On same-language queries it is close to dense (EN 0.892 vs 0.955, AR 0.852 vs 0.951) at 11 ms p50 against 141 ms. It handles exact identifiers, numbers and codes in filter-heavy queries, and it gives the reranker a lexical second opinion: hybrid + rerank beats dense + nothing on EN, AR and cross-lingual queries. The queries were written as paraphrases, which favours dense retrieval. A query log full of codes and part numbers would shift the balance towards BM25.

**Arabic.** The `arabic` analyzer's normalisation works: `ar21`, written without hamza («اجراء العزل والاقفال»), retrieves the hamza-spelled LOTO-001 Arabic procedure at rank 1 in every mode. `ar22` shows the opposite failure for dense: «ارتفاع حرارة المحمل» ("high bearing temperature") pulls the heat-stress procedure to dense rank 1, while BM25 and every hybrid mode rank the crusher bearing manual first. Arabic nDCG is within 0.02 of English for dense and for hybrid + rerank.

**Cross-lingual is the weakest group in all modes**, and the per-query runs show why fusion alone hurts it:
- **`x04` and `x05`** (Arabic queries, English-only answers): dense ranks the answer first; both fusions replace it with an Arabic document that BM25 matched on shared words; rerank restores the right answer to rank 1.
- **`x01`** (brake lining, answer only in Arabic) is the hard case. No first-stage mode puts `MM-HT-003-AR` in the top 10, because the English 250-hour service manual, which mentions brake wear, wins on both engines. Rerank only lifts it to rank 9.

**Versions.** With the version filter off, the best mode ranks a superseded revision first on 4 of 12 version-trap queries. Old and new revisions are near-duplicates, so no ranker can be trusted to tell them apart. Validity has to be a filter (`latest_only` / `as_of`), not a ranking signal.

**Latency is the cost.** On 4 CPU cores the cross-encoder scores about 1 pair per second, so reranking 30 candidates takes ~31 s per query (p50 30.8 s). That's fine for offline eval, not for chat. Options, in order of preference:
1. A GPU (M11, or the GKE GPU pool in M9): expected 50–100× faster.
2. Rerank fewer candidates: 10 candidates ≈ 10 s.
3. An int8/ONNX reranker.

The fusion default stays RRF (ADR-0002), since the agent always reranks. A follow-up worth measuring: weighted RRF, or skipping BM25 when the query language has no lexical overlap with the candidate set.
