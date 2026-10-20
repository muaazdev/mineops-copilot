from __future__ import annotations

from pathlib import Path

import pytest

from mineops_core.settings import get_settings
from mineops_retrieval.tokens import HFTokenCounter, hf_token_counter

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "data" / "corpus"


@pytest.fixture(scope="session")
def counter() -> HFTokenCounter:
    s = get_settings().search
    return hf_token_counter(s.embed_model, s.embed_revision)


@pytest.fixture(scope="session")
def corpus_dir() -> Path:
    return CORPUS


# --- integration fixtures: real OpenSearch + Qdrant via testcontainers -----------------------
from collections.abc import Iterator  # noqa: E402

from testcontainers.community.opensearch import OpenSearchContainer  # noqa: E402
from testcontainers.community.qdrant import QdrantContainer  # noqa: E402

from mineops_core.settings import SearchSettings  # noqa: E402
from mineops_retrieval.chunking import chunk_corpus  # noqa: E402
from mineops_retrieval.embedders import HashingEmbedder  # noqa: E402
from mineops_retrieval.ingest import IngestReport, ingest  # noqa: E402
from mineops_retrieval.models import Chunk  # noqa: E402
from mineops_retrieval.opensearch_store import OpenSearchStore  # noqa: E402
from mineops_retrieval.qdrant_store import QdrantStore  # noqa: E402
from mineops_retrieval.rerank import OverlapReranker  # noqa: E402
from mineops_retrieval.retriever import HybridRetriever  # noqa: E402

OPENSEARCH_IMAGE = "opensearchproject/opensearch:3.9.0"
QDRANT_IMAGE = "qdrant/qdrant:v1.19.2"


@pytest.fixture(scope="session")
def opensearch_url() -> Iterator[str]:
    c = (
        OpenSearchContainer(OPENSEARCH_IMAGE)
        .with_env("DISABLE_INSTALL_DEMO_CONFIG", "true")
        .with_env("OPENSEARCH_JAVA_OPTS", "-Xms512m -Xmx512m")
        # Absolute free-space watermarks: CI runners and sandboxes report high disk % used.
        .with_env("cluster.routing.allocation.disk.watermark.low", "2gb")
        .with_env("cluster.routing.allocation.disk.watermark.high", "1gb")
        .with_env("cluster.routing.allocation.disk.watermark.flood_stage", "500mb")
    )
    with c:
        yield f"http://{c.get_container_host_ip()}:{c.get_exposed_port(9200)}"


@pytest.fixture(scope="session")
def qdrant_url() -> Iterator[str]:
    with QdrantContainer(QDRANT_IMAGE) as c:
        yield f"http://{c.get_container_host_ip()}:{c.exposed_rest_port}"


@pytest.fixture(scope="session")
def search_settings(opensearch_url: str, qdrant_url: str) -> SearchSettings:
    return SearchSettings(embedder="hashing", opensearch_url=opensearch_url, qdrant_url=qdrant_url)


@pytest.fixture(scope="session")
def stores(search_settings: SearchSettings) -> tuple[OpenSearchStore, QdrantStore]:
    s = search_settings
    return (
        OpenSearchStore(s.opensearch_url, s.opensearch_index),
        QdrantStore(s.qdrant_url, s.qdrant_collection),
    )


@pytest.fixture(scope="session")
def ingested(
    search_settings: SearchSettings,
    stores: tuple[OpenSearchStore, QdrantStore],
    corpus_dir: Path,
) -> IngestReport:
    return ingest(corpus_dir, search_settings, HashingEmbedder(), stores)


@pytest.fixture(scope="session")
def chunks(counter: HFTokenCounter, corpus_dir: Path) -> list[Chunk]:
    return chunk_corpus(corpus_dir, counter)


@pytest.fixture(scope="session")
def retriever(
    stores: tuple[OpenSearchStore, QdrantStore], ingested: IngestReport
) -> Iterator[HybridRetriever]:
    r = HybridRetriever(stores[0], stores[1], HashingEmbedder(), OverlapReranker())
    yield r
    r.close()
