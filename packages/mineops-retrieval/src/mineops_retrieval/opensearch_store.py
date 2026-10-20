"""OpenSearch BM25 index for chunks.

Why it is built this way (see also docs/interview/M02.md):

* **Index template + versioned index + alias.** The template holds settings/mappings for any
  index matching ``<alias>-v*``. Ingestion writes a fresh ``<alias>-v<N>`` index and then moves
  the alias atomically, so a re-ingest (new analyzer, new chunking) never serves a half-built
  index and rollback is an alias flip. Queries always go through the alias.
* **One shard, zero replicas** locally: 65 chunks fit trivially in one shard, and a single-node
  cluster cannot place replicas anyway (they would leave the index yellow). Production raises
  replicas, not shards.
* **Multi-field text.** ``text`` is indexed three times from one source value:
  ``text`` (``standard`` analyzer: lowercase + Unicode word split; language-neutral),
  ``text.en`` (``english``: stop words + Porter stemming, so "inspections" ~ "inspect"),
  ``text.ar`` (``arabic``: Arabic stop words, normalisation of alef/hamza/yeh/teh marbuta
  variants and diacritics, Arabic-Indic digit folding, light stemming that strips prefixes such
  as ال/و/ب and common suffixes). Indexing every document into both language subfields costs a
  little disk but lets one query reach any document through the analyzer matching the *query*.
* **Keyword fields** for every filter (exact, not analysed), ``date`` for the validity window,
  ``boolean`` for ``is_latest``. Filters run in filter context: cached bitsets, no score effect.
* **BM25 defaults kept** (k1=1.2 term-frequency saturation, b=0.75 length normalisation).
  Chunks are length-capped by the chunker, so ``b`` has little to correct, and we have no
  held-out dev set to tune k1/b without overfitting the 60-query eval.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from opensearchpy import OpenSearch, helpers

from mineops_retrieval.filters import RetrievalFilter, to_opensearch
from mineops_retrieval.models import Chunk, Lang

LANG_FIELDS: dict[Lang, list[str]] = {
    # Title boosted x2: a title match is strong evidence the whole chunk is on-topic.
    "en": ["title.en^2", "text.en"],
    "ar": ["title.ar^2", "text.ar"],
}
# Fallback clause: every analysed field, low weight. Catches language-independent tokens that
# appear in documents of the *other* language — procedure codes (LOTO-001), numbers, acronyms
# (WBGT, MCC) — without letting cross-language noise outrank a proper same-language match.
FALLBACK_FIELDS = ["title^2", "text", "title.en^2", "text.en", "title.ar^2", "text.ar"]
FALLBACK_BOOST = 0.3

_TEXT_FIELD = {
    "type": "text",
    "analyzer": "standard",
    "fields": {
        "en": {"type": "text", "analyzer": "english"},
        "ar": {"type": "text", "analyzer": "arabic"},
    },
}

MAPPINGS: dict[str, Any] = {
    # strict: a typo in an ingest field fails loudly instead of creating a new dynamic field.
    "dynamic": "strict",
    "properties": {
        "chunk_id": {"type": "keyword"},
        "doc_id": {"type": "keyword"},
        "code": {"type": "keyword"},
        "chunk_idx": {"type": "integer"},
        "section_path": {"type": "keyword"},
        "title": _TEXT_FIELD,
        "text": _TEXT_FIELD,
        "doc_type": {"type": "keyword"},
        "site": {"type": "keyword"},
        "asset_type": {"type": "keyword"},
        "lang": {"type": "keyword"},
        "version": {"type": "integer"},
        "effective_date": {"type": "date", "format": "strict_date"},
        "supersedes": {"type": "keyword"},
        "superseded_on": {"type": "date", "format": "strict_date"},
        "is_latest": {"type": "boolean"},
        "n_tokens": {"type": "integer"},
    },
}

SETTINGS: dict[str, Any] = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    # Explicit so the choice is visible; these are OpenSearch's BM25 defaults.
    "similarity": {"default": {"type": "BM25", "k1": 1.2, "b": 0.75}},
}


def build_query(query: str, lang: Lang, flt: RetrievalFilter, size: int) -> dict[str, Any]:
    """Language-routed BM25 query with a low-weight cross-language fallback."""
    return {
        "size": size,
        "track_total_hits": False,
        "_source": True,
        "query": {
            "bool": {
                "filter": to_opensearch(flt),
                "should": [
                    {
                        # best_fields: score = best single field (title or text), so a term
                        # repeated in title and body is not double counted.
                        "multi_match": {
                            "query": query,
                            "fields": LANG_FIELDS[lang],
                            "type": "best_fields",
                        }
                    },
                    {
                        "multi_match": {
                            "query": query,
                            "fields": FALLBACK_FIELDS,
                            "type": "best_fields",
                            "boost": FALLBACK_BOOST,
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
    }


class OpenSearchStore:
    def __init__(self, url: str, alias: str, client: OpenSearch | None = None) -> None:
        self.alias = alias
        self.client = client or OpenSearch(hosts=[url], timeout=30)

    # --- schema --------------------------------------------------------------------------
    def ensure_template(self) -> None:
        self.client.indices.put_index_template(
            name=f"{self.alias}-template",
            body={
                "index_patterns": [f"{self.alias}-v*"],
                "template": {"settings": SETTINGS, "mappings": MAPPINGS},
                "priority": 100,
            },
        )

    def _next_index(self) -> str:
        existing = self.client.indices.get(index=f"{self.alias}-v*", ignore_unavailable=True)
        versions = [int(name.rsplit("-v", 1)[1]) for name in existing]
        return f"{self.alias}-v{max(versions, default=0) + 1}"

    # --- ingest ----------------------------------------------------------------------------
    def rebuild(self, chunks: Iterable[Chunk]) -> str:
        """Index into a new versioned index, swap the alias, delete older versions."""
        self.ensure_template()
        index = self._next_index()
        self.client.indices.create(index=index)
        actions = (
            {"_op_type": "index", "_index": index, "_id": c.chunk_id, "_source": c.payload()}
            for c in chunks
        )
        helpers.bulk(self.client, actions, refresh=True)
        old = list(self.client.indices.get(index=f"{self.alias}-v*", ignore_unavailable=True))
        swap: list[dict[str, Any]] = [
            {"remove": {"index": name, "alias": self.alias}}
            for name in old
            if name != index and self.client.indices.exists_alias(index=name, name=self.alias)
        ]
        swap.append({"add": {"index": index, "alias": self.alias}})
        self.client.indices.update_aliases(body={"actions": swap})
        for name in old:
            if name != index:
                self.client.indices.delete(index=name)
        return index

    def count(self) -> int:
        return int(self.client.count(index=self.alias)["count"])

    # --- search ----------------------------------------------------------------------------
    def search(
        self, query: str, lang: Lang, flt: RetrievalFilter, size: int
    ) -> list[tuple[Chunk, float]]:
        resp = self.client.search(index=self.alias, body=build_query(query, lang, flt, size))
        return [
            (Chunk.model_validate(h["_source"]), float(h["_score"])) for h in resp["hits"]["hits"]
        ]

    def filter_ids(self, flt: RetrievalFilter, size: int = 1000) -> set[str]:
        """All chunk IDs passing a filter (used to cross-check translators in tests)."""
        body = {"size": size, "_source": False, "query": {"bool": {"filter": to_opensearch(flt)}}}
        return {h["_id"] for h in self.client.search(index=self.alias, body=body)["hits"]["hits"]}

    def analyze(self, analyzer: str, text: str) -> Sequence[str]:
        resp = self.client.indices.analyze(body={"analyzer": analyzer, "text": text})
        return [t["token"] for t in resp["tokens"]]
