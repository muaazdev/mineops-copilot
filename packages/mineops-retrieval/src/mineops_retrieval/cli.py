"""``mineops-retrieval`` CLI: ingest the corpus and run ad-hoc searches."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from mineops_core.logging import configure_logging
from mineops_core.settings import get_settings
from mineops_retrieval.filters import RetrievalFilter
from mineops_retrieval.ingest import ingest, make_retriever
from mineops_retrieval.models import Mode

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def _main() -> None:
    s = get_settings()
    configure_logging("mineops-retrieval", s.log.level, s.log.json_format)


@app.command("ingest")
def ingest_cmd(
    corpus: Annotated[Path, typer.Option(help="corpus directory")] = Path("data/corpus"),
) -> None:
    """Chunk, embed and (re)index the corpus into OpenSearch and Qdrant."""
    report = ingest(corpus, get_settings().search)
    typer.echo(json.dumps(dataclasses.asdict(report)))


@app.command("search")
def search_cmd(
    query: str,
    mode: Annotated[Mode, typer.Option()] = Mode.hybrid_rerank,
    k: Annotated[int, typer.Option()] = 5,
    site: Annotated[str | None, typer.Option()] = None,
    asset_type: Annotated[str | None, typer.Option()] = None,
    as_of: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])] = None,
    all_versions: Annotated[bool, typer.Option(help="include superseded revisions")] = False,
) -> None:
    """Search and print hits with per-stage scores."""
    flt = RetrievalFilter(
        site=site,
        asset_type=asset_type,
        as_of=as_of.date() if as_of else None,
        latest_only=not all_versions,
    )
    retriever = make_retriever(get_settings().search, with_reranker=mode == Mode.hybrid_rerank)
    res = retriever.search(query, flt, mode, k)
    for h in res.hits:
        sec = h.chunk.section_path[0] if h.chunk.section_path else ""
        stages = " ".join(f"{s}={v:.3f}#{h.ranks.get(s)}" for s, v in h.scores.items())
        typer.echo(f"[{h.chunk.doc_id} §{sec}] {h.chunk.title}  ({stages})")
    typer.echo(json.dumps({"lang": res.query_lang, "timings_ms": res.timings_ms}))
