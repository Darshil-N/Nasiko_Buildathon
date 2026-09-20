"""Pydantic schemas for the standard error envelope (architecture section 10.4)."""

from pydantic import BaseModel, ConfigDict

from backend.app.core.errors import ErrorCode


class ErrorDetail(BaseModel):
    """Specific validation problem."""

    model_config = ConfigDict(extra="allow")

    field: str | None = None
    problem: str


class ErrorBody(BaseModel):
    """The body of an error response."""

    code: ErrorCode
    message: str
    retryable: bool
    details: list[ErrorDetail] | None = None
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    """Standard error response envelope."""

    error: ErrorBody
