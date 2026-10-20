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
