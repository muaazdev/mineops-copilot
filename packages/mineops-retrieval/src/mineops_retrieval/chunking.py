"""Heading-aware markdown chunking.

Strategy: split the body at H2 headings, then greedily pack whole sections into chunks of at
most ``max_tokens``. A section larger than the budget is split on line boundaries with
``overlap_tokens`` of trailing context carried into the next piece. Every chunk starts with the
document title so both BM25 and the embedder see document context even for a mid-document
chunk; ``section_path`` keeps the sections for citations (``[doc_id §section]``). A fragment
smaller than ``min_tokens`` is merged into a neighbouring chunk (soft cap 1.2x budget)
instead of becoming a near-empty chunk that would rank on boilerplate alone.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from mineops_retrieval.models import Chunk
from mineops_retrieval.tokens import TokenCounter

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_H1 = re.compile(r"^# (.+)$", re.MULTILINE)
_H2 = re.compile(r"^## (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ParsedDoc:
    meta: dict[str, Any]
    title: str
    sections: list[tuple[str, str]]  # (heading, text)


def parse_markdown(text: str) -> ParsedDoc:
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError("document has no YAML frontmatter")
    meta: dict[str, Any] = yaml.safe_load(m.group(1))
    body = text[m.end() :]
    h1 = _H1.search(body)
    title = h1.group(1).strip() if h1 else str(meta["title"])
    heads = list(_H2.finditer(body))
    sections: list[tuple[str, str]] = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        content = body[h.end() : end].strip()
        if content:
            sections.append((h.group(1).strip(), content))
    return ParsedDoc(meta=meta, title=title, sections=sections)


def _split_long(text: str, budget: int, overlap: int, counter: TokenCounter) -> list[str]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    pieces: list[str] = []
    cur: list[str] = []
    for line in lines:
        if cur and counter.count("\n".join([*cur, line])) > budget:
            pieces.append("\n".join(cur))
            # Carry trailing lines (up to ``overlap`` tokens) into the next piece.
            carry: list[str] = []
            for prev in reversed(cur):
                if counter.count("\n".join([prev, *carry])) > overlap:
                    break
                carry.insert(0, prev)
            cur = carry
        cur.append(line)
    if cur:
        pieces.append("\n".join(cur))
    return pieces


def chunk_document(
    doc: ParsedDoc,
    counter: TokenCounter,
    max_tokens: int = 550,
    overlap_tokens: int = 60,
    min_tokens: int = 120,
) -> list[Chunk]:
    meta = doc.meta
    Unit = tuple[list[str], str]  # (section headings, text)

    def render(group: list[Unit]) -> tuple[list[str], str]:
        path: list[str] = []
        for heads, _ in group:
            path.extend(h for h in heads if h not in path)
        body = "\n\n".join(f"## {heads[0]}\n{text}" for heads, text in group)
        return path, f"{doc.title}\n\n{body}"

    def size(group: list[Unit]) -> int:
        return counter.count(render(group)[1])

    # 1. Units: one per section; oversized sections are split with overlap.
    units: list[Unit] = []
    for heading, text in doc.sections:
        budget = max(max_tokens - counter.count(f"{doc.title}\n\n## {heading}\n"), 32)
        if counter.count(text) <= budget:
            units.append(([heading], text))
        else:
            units.extend(
                ([heading], piece) for piece in _split_long(text, budget, overlap_tokens, counter)
            )

    # 2. Greedy packing of whole units up to the budget.
    groups: list[list[Unit]] = [[]]
    for unit in units:
        if groups[-1] and size([*groups[-1], unit]) > max_tokens:
            groups.append([])
        groups[-1].append(unit)

    # 3. Fold any fragment below ``min_tokens`` into a neighbour (next first, then previous)
    #    if the merged chunk stays within the soft cap of 1.2x the budget.
    cap = int(max_tokens * 1.2)
    i = 0
    while len(groups) > 1 and i < len(groups):
        if size(groups[i]) < min_tokens:
            if i + 1 < len(groups) and size([*groups[i], *groups[i + 1]]) <= cap:
                groups[i : i + 2] = [[*groups[i], *groups[i + 1]]]
                continue
            if i > 0 and size([*groups[i - 1], *groups[i]]) <= cap:
                groups[i - 1 : i + 1] = [[*groups[i - 1], *groups[i]]]
                i -= 1
                continue
        i += 1

    chunks: list[Chunk] = []
    for idx, group in enumerate(g for g in groups if g):
        path, text = render(group)
        chunks.append(
            Chunk(
                chunk_id=f"{meta['doc_id']}#{idx}",
                doc_id=meta["doc_id"],
                code=str(meta["doc_id"]).rsplit("-", 2)[0],
                chunk_idx=idx,
                section_path=path,
                title=doc.title,
                text=text,
                doc_type=meta["doc_type"],
                site=meta["site"],
                asset_type=meta["asset_type"],
                lang=meta["lang"],
                version=int(meta["version"]),
                effective_date=meta["effective_date"],
                supersedes=meta.get("supersedes"),
                n_tokens=counter.count(text),
            )
        )
    return chunks


def mark_versions(chunks: Iterable[Chunk]) -> list[Chunk]:
    """Set ``superseded_on`` / ``is_latest`` from the corpus-wide supersedes graph."""
    chunks = list(chunks)
    effective: dict[str, date] = {c.doc_id: c.effective_date for c in chunks}
    superseded_on: dict[str, date] = {
        c.supersedes: effective[c.doc_id] for c in chunks if c.supersedes
    }
    return [
        c.model_copy(
            update={
                "superseded_on": superseded_on.get(c.doc_id),
                "is_latest": c.doc_id not in superseded_on,
            }
        )
        for c in chunks
    ]


def chunk_corpus(
    corpus_dir: Path, counter: TokenCounter, max_tokens: int = 550, overlap_tokens: int = 60
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        doc = parse_markdown(path.read_text(encoding="utf-8"))
        chunks.extend(chunk_document(doc, counter, max_tokens, overlap_tokens))
    return mark_versions(chunks)
