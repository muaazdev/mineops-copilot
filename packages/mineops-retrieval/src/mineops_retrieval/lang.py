"""Query language detection by script. Arabic and English do not share an alphabet, so the share
of Arabic letters is a reliable, dependency-free signal for routing to the right analyzer."""

from __future__ import annotations

from mineops_retrieval.models import Lang


def _is_arabic(ch: str) -> bool:
    cp = ord(ch)
    return 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x08A0 <= cp <= 0x08FF


def detect_lang(text: str, threshold: float = 0.3) -> Lang:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    share = sum(1 for c in letters if _is_arabic(c)) / len(letters)
    return "ar" if share >= threshold else "en"
