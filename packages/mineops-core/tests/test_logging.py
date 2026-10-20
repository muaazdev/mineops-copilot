import json
import logging

import pytest

from mineops_core.logging import JsonFormatter, configure_logging, log_context, request_id_var


def _record(msg: str, **extra: object) -> logging.LogRecord:
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_required_fields_and_context() -> None:
    fmt = JsonFormatter("svc")
    with log_context(request_id="req-1", trace_id="tr-1"):
        out = json.loads(fmt.format(_record("hello", site="FRN")))
    assert {"ts", "level", "service", "request_id", "trace_id", "msg"} <= out.keys()
    assert out["service"] == "svc"
    assert out["request_id"] == "req-1"
    assert out["trace_id"] == "tr-1"
    assert out["site"] == "FRN"
    assert request_id_var.get() is None


def test_arabic_not_escaped() -> None:
    out = JsonFormatter("svc").format(_record("مرحبا"))
    assert "مرحبا" in out


def test_configure_logging_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("svc", "INFO")
    logging.getLogger("x").info("one line", extra={"k": 1})
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(line)["k"] == 1
