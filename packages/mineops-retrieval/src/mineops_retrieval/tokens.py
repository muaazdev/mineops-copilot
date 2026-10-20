"""Token counting with the embedder's own tokenizer, so chunk sizes mean what the model sees.

Only ``tokenizer.json`` (~17 MB) is fetched from the pinned BGE-M3 revision; no torch needed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class HFTokenCounter:
    def __init__(self, model: str, revision: str) -> None:
        path = hf_hub_download(model, "tokenizer.json", revision=revision)
        self._tok = Tokenizer.from_file(path)

    def count(self, text: str) -> int:
        return len(self._tok.encode(text, add_special_tokens=False).ids)


@lru_cache(maxsize=4)
def hf_token_counter(model: str, revision: str) -> HFTokenCounter:
    return HFTokenCounter(model, revision)
