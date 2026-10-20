import pytest

from mineops_core.settings import DbSettings, MineOpsSettings


def test_env_prefix_and_nesting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINEOPS_SERVICE_NAME", "mcp-server")
    monkeypatch.setenv("MINEOPS_DB__HOST", "db.internal")
    monkeypatch.setenv("MINEOPS_DB__PORT", "6543")
    monkeypatch.setenv("MINEOPS_DB__PASSWORD", "s3cret")
    monkeypatch.setenv("MINEOPS_LOG__LEVEL", "DEBUG")
    s = MineOpsSettings(_env_file=None)  # type: ignore[call-arg]
    assert s.service_name == "mcp-server"
    assert s.db.host == "db.internal"
    assert s.db.port == 6543
    assert s.log.level == "DEBUG"
    assert "s3cret" not in repr(s)


def test_db_url_and_conninfo() -> None:
    db = DbSettings(host="h", port=1, name="n", user="u", password="p")  # type: ignore[arg-type]
    assert db.url() == "postgresql+psycopg://u:p@h:1/n"
    assert db.conninfo() == "host=h port=1 dbname=n user=u password=p"
    assert DbSettings(user="u").url().startswith("postgresql+psycopg://u@")


def test_rejects_bad_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINEOPS_LOG__LEVEL", "LOUD")
    with pytest.raises(ValueError):
        MineOpsSettings(_env_file=None)  # type: ignore[call-arg]
