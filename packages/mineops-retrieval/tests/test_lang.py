import pytest

from mineops_retrieval.lang import detect_lang


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("How often is the engine oil changed?", "en"),
        ("كم مرة يتم تغيير زيت المحرك؟", "ar"),
        ("ما هو حد WBGT لإيقاف العمل؟", "ar"),  # mixed script, mostly Arabic
        ("LOTO-001 group lock box", "en"),
        ("12345", "en"),
        ("", "en"),
    ],
)
def test_detect_lang(text: str, lang: str) -> None:
    assert detect_lang(text) == lang
