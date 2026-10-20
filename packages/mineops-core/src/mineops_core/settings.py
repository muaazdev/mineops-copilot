"""Central configuration. The only place env vars are read (CLAUDE.md: config conventions)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DbSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str = "mineops"
    user: str = "mineops_owner"
    password: SecretStr = SecretStr("")
    statement_timeout_ms: int = Field(default=5000, ge=0)

    def url(self, driver: str = "postgresql+psycopg") -> str:
        """SQLAlchemy URL. The password is only revealed here, never logged."""
        pw = self.password.get_secret_value()
        auth = f"{self.user}:{pw}" if pw else self.user
        return f"{driver}://{auth}@{self.host}:{self.port}/{self.name}"

    def conninfo(self) -> str:
        """libpq conninfo string for raw psycopg connections."""
        parts = {
            "host": self.host,
            "port": str(self.port),
            "dbname": self.name,
            "user": self.user,
        }
        pw = self.password.get_secret_value()
        if pw:
            parts["password"] = pw
        return " ".join(f"{k}={v}" for k, v in parts.items())


class LogSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    json_format: bool = True


class SearchSettings(BaseModel):
    """Retrieval stack (M2). Model revisions are pinned so embeddings are reproducible."""

    # "bge-m3" = SentenceTransformer models below; "hashing" = model-free lexical embedder and
    # overlap reranker (tests, or machines without torch). Never mix embedders in one index.
    embedder: Literal["bge-m3", "hashing"] = "bge-m3"
    opensearch_url: str = "http://localhost:9200"
    opensearch_index: str = "mineops-chunks"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "mineops_chunks"
    embed_model: str = "BAAI/bge-m3"
    embed_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_revision: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    device: str = "cpu"
    rrf_k: int = Field(default=60, ge=1)
    candidates: int = Field(default=30, ge=1)  # per engine, and rerank input size
    top_k: int = Field(default=8, ge=1)  # rerank output size
    chunk_max_tokens: int = Field(default=550, ge=64)
    chunk_overlap_tokens: int = Field(default=60, ge=0)


class MineOpsSettings(BaseSettings):
    """Base settings; services subclass and add their own sections.

    Env vars: ``MINEOPS_SERVICE_NAME``, ``MINEOPS_DB__HOST``, ``MINEOPS_LOG__LEVEL`` ...
    """

    model_config = SettingsConfigDict(
        env_prefix="MINEOPS_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "mineops"
    environment: Literal["local", "ci", "kind", "gke"] = "local"
    db: DbSettings = DbSettings()
    log: LogSettings = LogSettings()
    search: SearchSettings = SearchSettings()


@lru_cache(maxsize=1)
def get_settings() -> MineOpsSettings:
    return MineOpsSettings()
