from mineops_core.errors import ErrorEnvelope, ForbiddenError, MineOpsError
from mineops_core.logging import log_context


def test_envelope_shape() -> None:
    err = ForbiddenError("site not allowed", details={"site": "WSP"})
    env = err.to_envelope(request_id="r1").model_dump()
    assert env == {
        "error": {
            "code": "FORBIDDEN",
            "message": "site not allowed",
            "request_id": "r1",
            "details": {"site": "WSP"},
        }
    }
    assert err.http_status == 403


def test_request_id_from_context_and_overrides() -> None:
    err = MineOpsError("boom", code="CUSTOM", http_status=418)
    with log_context(request_id="ctx"):
        env = err.to_envelope()
    assert env.error.request_id == "ctx"
    assert (err.code, err.http_status) == ("CUSTOM", 418)
    assert ErrorEnvelope.model_validate(env.model_dump()) == env
