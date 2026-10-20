"""Domain errors and the shared error envelope (same shape in every service)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mineops_core.logging import request_id_var


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class MineOpsError(Exception):
    """Base for all domain errors. Subclasses set ``code`` and ``http_status``."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or {}

    def to_envelope(self, request_id: str | None = None) -> ErrorEnvelope:
        return ErrorEnvelope(
            error=ErrorBody(
                code=self.code,
                message=self.message,
                request_id=request_id if request_id is not None else request_id_var.get(),
                details=self.details,
            )
        )


class ValidationError(MineOpsError):
    code = "VALIDATION_ERROR"
    http_status = 422


class NotFoundError(MineOpsError):
    code = "NOT_FOUND"
    http_status = 404


class ForbiddenError(MineOpsError):
    code = "FORBIDDEN"
    http_status = 403


class ConflictError(MineOpsError):
    code = "CONFLICT"
    http_status = 409
