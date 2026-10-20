"""Retrieval eval: BM25 vs dense vs hybrid (RRF / weighted) vs hybrid + rerank.

    make ingest && make eval-retrieval

Reads data/eval/{queries,qrels}.jsonl, queries the live OpenSearch + Qdrant indexes through
HybridRetriever, evaluates at document level (chunks deduplicated to doc_id in rank order),
and writes eval/results/retrieval.{md,json} (committed) plus per-query runs to
eval/results/raw/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from mineops_core.logging import configure_logging
from mineops_core.settings import get_settings
from mineops_retrieval.filters import RetrievalFilter
from mineops_retrieval.ingest import make_retriever
from mineops_retrieval.metrics import dedupe, percentile, summarise
from mineops_retrieval.models import Mode
from mineops_retrieval.retriever import HybridRetriever

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_MARKER = "<!-- analysis: hand-written, preserved by retrieval_eval.py -->"
GROUPS = ("en", "ar", "cross")
MODE_LABEL = {
    Mode.bm25: "BM25 (OpenSearch)",
    Mode.dense: "Dense (Qdrant)",
    Mode.hybrid_weighted: "Hybrid weighted (min-max 0.5/0.5)",
    Mode.hybrid: "Hybrid RRF (k=60)",
    Mode.hybrid_rerank: "Hybrid RRF + rerank (30→10)",
}


def load(eval_dir: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    queries = [json.loads(line) for line in (eval_dir / "queries.jsonl").open(encoding="utf-8")]
    qrels: dict[str, dict[str, int]] = defaultdict(dict)
    for line in (eval_dir / "qrels.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        qrels[r["qid"]][r["doc_id"]] = int(r["rel"])
    return queries, dict(qrels)


def to_filter(raw: dict[str, Any], latest_only: bool = True) -> RetrievalFilter:
    as_of = raw.get("as_of")
    return RetrievalFilter(
        site=raw.get("site"),
        asset_type=raw.get("asset_type"),
        doc_type=raw.get("doc_type"),
        lang=raw.get("lang"),
        as_of=date.fromisoformat(as_of) if as_of else None,
        latest_only=latest_only,
    )


def run_mode(
    r: HybridRetriever, mode: Mode, queries: list[dict[str, Any]], k: int, latest_only: bool = True
) -> tuple[dict[str, list[str]], dict[str, float]]:
    runs: dict[str, list[str]] = {}
    latency: dict[str, float] = {}
    r.search(queries[0]["query"], mode=mode, k=k)  # warm-up: exclude lazy init from latency
    for q in queries:
        t = time.perf_counter()
        res = r.search(q["query"], to_filter(q["filter"], latest_only), mode, k=2 * k)
        latency[q["qid"]] = (time.perf_counter() - t) * 1000
        runs[q["qid"]] = dedupe([h.chunk.doc_id for h in res.hits])[:k]
    return runs, latency


def stale_at_top(ranked: list[str], qrels: dict[str, int]) -> bool:
    """Rank 1 is an unjudged revision of the same document series as the answer."""
    if not ranked or qrels.get(ranked[0], 0) > 0:
        return False
    answer = max(qrels, key=lambda d: qrels[d])
    return ranked[0].rsplit("-R", 1)[0] == answer.rsplit("-R", 1)[0]


def fmt(x: float) -> str:
    return f"{x:.3f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eval-dir", type=Path, default=ROOT / "data" / "eval")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--modes", nargs="*", default=[m.value for m in MODE_LABEL])
    args = ap.parse_args()

    s = get_settings()
    configure_logging("retrieval-eval", "WARNING", s.log.json_format)
    modes = [Mode(m) for m in args.modes]
    retriever = make_retriever(s.search, with_reranker=Mode.hybrid_rerank in modes)
    if retriever.os.count() == 0 or retriever.qd.count() == 0:
        raise SystemExit("indexes are empty: run `make ingest` first")

    queries, qrels = load(args.eval_dir)
    by_group = {g: [q["qid"] for q in queries if q["group"] == g] for g in GROUPS}
    results: dict[str, Any] = {"modes": {}}
    raw: dict[str, Any] = {}
    for mode in modes:
        t0 = time.perf_counter()
        runs, lat = run_mode(retriever, mode, queries, args.k)
        overall = summarise(runs, qrels)
        overall |= {
            "p50_ms": percentile(list(lat.values()), 50),
            "p95_ms": percentile(list(lat.values()), 95),
        }
        groups = {g: summarise({q: runs[q] for q in ids}, qrels) for g, ids in by_group.items()}
        results["modes"][mode.value] = {"overall": overall, "groups": groups}
        raw[mode.value] = {"runs": runs, "latency_ms": lat}
        print(f"{mode.value:16s} ndcg@10={overall['ndcg@10']:.3f} "
              f"({time.perf_counter() - t0:.0f}s)", flush=True)  # fmt: skip

    # Ablation: what the version filter buys. Without latest_only, how often does a
    # superseded revision outrank the current one on the version-trap queries?
    traps = [q for q in queries if "superseded_trap" in q["tags"]]
    abl_mode = modes[-1]
    runs, _ = run_mode(retriever, abl_mode, traps, args.k, latest_only=False)
    stale_top1 = sum(1 for q in traps if stale_at_top(runs[q["qid"]], qrels[q["qid"]]))
    results["ablation_no_version_filter"] = {
        "mode": abl_mode.value,
        "trap_queries": len(traps),
        "superseded_revision_at_rank1": stale_top1,
    }

    os_store = retriever.os
    results["meta"] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "queries": len(queries),
        "by_group": {g: len(v) for g, v in by_group.items()},
        "qrels": sum(len(v) for v in qrels.values()),
        "chunks_indexed": os_store.count(),
        "embedder": retriever.embedder.name,
        "reranker": retriever.reranker.name if retriever.reranker else None,
        "k": args.k,
        "candidates": retriever.candidates,
        "rrf_k": retriever.rrf_k,
        "machine": f"{platform.machine()}, {os.cpu_count()} CPU, {s.search.device}",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "retrieval.json").write_text(json.dumps(results, indent=2) + "\n")
    (args.out / "raw").mkdir(exist_ok=True)
    (args.out / "raw" / "retrieval_runs.json").write_text(json.dumps(raw, indent=1) + "\n")
    md_path = args.out / "retrieval.md"
    # Keep the hand-written analysis (everything from ANALYSIS_MARKER on) across re-runs.
    old = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    tail = old[old.index(ANALYSIS_MARKER) :] if ANALYSIS_MARKER in old else ""
    md_path.write_text(render_md(results) + ("\n" + tail if tail else ""), encoding="utf-8")
    retriever.close()
    print(f"wrote {args.out / 'retrieval.md'}")


def render_md(res: dict[str, Any]) -> str:
    m = res["meta"]
    lines = [
        "# Retrieval eval",
        "",
        f"{m['queries']} queries ({m['by_group']['en']} EN, {m['by_group']['ar']} AR, "
        f"{m['by_group']['cross']} cross-lingual), {m['qrels']} graded judgements, "
        f"{m['chunks_indexed']} chunks. Embedder `{m['embedder']}`, reranker "
        f"`{m['reranker']}`, {m['candidates']} candidates per engine, RRF k={m['rrf_k']}. "
        f"Document-level metrics @{m['k']}. Latency is end-to-end per query on "
        f"{m['machine']} (generated {m['generated_at']}).",
        "",
        "## Overall",
        "",
        "| Mode | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | p50 ms | p95 ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for mode, r in res["modes"].items():
        o = r["overall"]
        lines.append(
            f"| {MODE_LABEL[Mode(mode)]} | {fmt(o['recall@5'])} | {fmt(o['recall@10'])} | "
            f"{fmt(o['mrr@10'])} | {fmt(o['ndcg@10'])} | {o['p50_ms']:.0f} | {o['p95_ms']:.0f} |"
        )
    lines += ["", "## By query language", ""]
    lines += [
        "| Mode | EN nDCG@10 | EN MRR@10 | AR nDCG@10 | AR MRR@10 | Cross nDCG@10 | Cross MRR@10 |",
        "|---|---|---|---|---|---|---|",
    ]
    for mode, r in res["modes"].items():
        g = r["groups"]
        lines.append(
            f"| {MODE_LABEL[Mode(mode)]} | "
            + " | ".join(f"{fmt(g[x]['ndcg@10'])} | {fmt(g[x]['mrr@10'])}" for x in GROUPS)
            + " |"
        )
    a = res["ablation_no_version_filter"]
    lines += [
        "",
        "## Version-filter ablation",
        "",
        f"With `latest_only=False`, mode `{a['mode']}` ranked a superseded revision first on "
        f"{a['superseded_revision_at_rank1']} of {a['trap_queries']} version-trap queries "
        "(0 with the default filter, by construction).",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
