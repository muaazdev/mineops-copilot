from __future__ import annotations

from datetime import date
from pathlib import Path

from mineops_retrieval.chunking import chunk_corpus, chunk_document, mark_versions, parse_markdown
from mineops_retrieval.tokens import HFTokenCounter

DOC = """---
doc_id: "TST-001-EN-R1"
title: "Test Doc"
doc_type: "sop"
site: "all"
asset_type: "pump"
lang: "en"
version: 1
effective_date: 2025-01-01
supersedes: null
---

# Test Doc

## 1. Purpose

{purpose}

## 2. Procedure

{steps}

## 3. References

- TST-002
"""


def make(purpose: str, steps: str) -> str:
    return DOC.format(purpose=purpose, steps=steps)


def test_parse_frontmatter_and_sections() -> None:
    doc = parse_markdown(make("Short purpose.", "1. Do it."))
    assert doc.meta["doc_id"] == "TST-001-EN-R1"
    assert doc.meta["effective_date"] == date(2025, 1, 1)
    assert [h for h, _ in doc.sections] == ["1. Purpose", "2. Procedure", "3. References"]


def test_small_doc_is_one_chunk_with_title_header(counter: HFTokenCounter) -> None:
    chunks = chunk_document(parse_markdown(make("Short purpose.", "1. Do it.")), counter)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_id == "TST-001-EN-R1#0" and c.code == "TST-001"
    assert c.text.startswith("Test Doc\n\n## 1. Purpose")
    assert c.section_path == ["1. Purpose", "2. Procedure", "3. References"]


def test_long_section_is_split_with_overlap_and_budget(counter: HFTokenCounter) -> None:
    steps = "\n".join(
        f"{i}. Inspect pump seal number {i} and record the leakage rate in the log."
        for i in range(1, 80)
    )
    chunks = chunk_document(parse_markdown(make("Purpose.", steps)), counter, 200, 40)
    assert len(chunks) > 3
    assert all(c.n_tokens <= int(200 * 1.2) for c in chunks)
    # Overlap: the last line of a procedure piece reappears at the start of the next piece.
    first_lines = chunks[2].text.splitlines()
    last_of_prev = chunks[1].text.splitlines()[-1]
    assert last_of_prev in first_lines
    # Tiny sections never stand alone: Purpose joins the first Procedure piece and the
    # References stub joins the last one.
    assert chunks[0].section_path == ["1. Purpose", "2. Procedure"]
    assert "3. References" in chunks[-1].section_path


def test_versions_marked(counter: HFTokenCounter) -> None:
    v1 = chunk_document(parse_markdown(make("Old.", "1. Old step.")), counter)[0]
    v2 = v1.model_copy(
        update={
            "doc_id": "TST-001-EN-R2",
            "chunk_id": "TST-001-EN-R2#0",
            "version": 2,
            "effective_date": date(2026, 3, 1),
            "supersedes": "TST-001-EN-R1",
        }
    )
    old, new = mark_versions([v1, v2])
    assert (old.is_latest, old.superseded_on) == (False, date(2026, 3, 1))
    assert (new.is_latest, new.superseded_on) == (True, None)


def test_real_corpus_chunk_sizes(counter: HFTokenCounter, corpus_dir: Path) -> None:
    chunks = chunk_corpus(corpus_dir, counter)
    sizes = sorted(c.n_tokens for c in chunks)
    assert len({c.doc_id for c in chunks}) == 64
    assert sizes[-1] <= int(550 * 1.2)
    assert sizes[len(sizes) // 2] >= 400  # median inside the 400-600 target
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert len({c.point_id for c in chunks}) == len(chunks)
    assert sum(not c.is_latest for c in chunks) >= 13
