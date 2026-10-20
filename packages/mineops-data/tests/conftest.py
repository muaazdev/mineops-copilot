"""Integration fixtures: one real Postgres 16 per test session (testcontainers), migrated with
the real Alembic scripts and loaded with the real COPY loader. No mocks of the database."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

from mineops_data.generator import generate, write_dataset
from mineops_data.loader import load

PG_IMAGE = "postgres:16.15"
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture(scope="session")
def pg() -> Iterator[PostgresContainer]:
    with PostgresContainer(
        PG_IMAGE, username="mineops_owner", password="test", dbname="mineops", driver="psycopg"
    ) as container:
        yield container


@pytest.fixture(scope="session")
def conninfo(pg: PostgresContainer) -> str:
    host, port = pg.get_container_host_ip(), pg.get_exposed_port(5432)
    return f"host={host} port={port} dbname=mineops user=mineops_owner password=test"


def alembic_cfg(pg: PostgresContainer) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", pg.get_connection_url())
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session")
def migrated(pg: PostgresContainer) -> PostgresContainer:
    command.upgrade(alembic_cfg(pg), "head")
    return pg


@pytest.fixture(scope="session")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("generated")
    write_dataset(generate(seed=42, scale="small"), out)
    return out


@pytest.fixture(scope="session")
def loaded(migrated: PostgresContainer, conninfo: str, generated: Path) -> dict[str, int]:
    return load(conninfo, generated)


@pytest.fixture(scope="session")
def ground_truth(generated: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((generated / "ground_truth.json").read_text("utf-8"))
    return data


@pytest.fixture
def db(conninfo: str, loaded: dict[str, int]) -> Iterator[psycopg.Connection[Any]]:
    """Owner connection; each test runs in a transaction that is rolled back."""
    with psycopg.connect(conninfo) as conn:
        yield conn
        conn.rollback()
