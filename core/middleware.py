"""
HTTP middleware — request tracing, structured logging, error handling.

Provides:
  - Request ID generation and propagation
  - Structured JSON logging per request
  - Standardized error response format
  - Request timing
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.security import AuditEntry, authenticate_request, check_rate_limit, sanitize_output, validate_input

logger = logging.getLogger("api.middleware")


# ---------------------------------------------------------------------------
# Structured logging setup
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Simple JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def configure_logging(json_output: bool = False) -> None:
    """Configure root logger. Use JSON format in production."""
    root = logging.getLogger()
    handler = logging.StreamHandler()

    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))

    root.addHandler(handler)


# ---------------------------------------------------------------------------
# Standard error response
# ---------------------------------------------------------------------------

ERROR_RESPONSES = {
    400: {"description": "Bad request — invalid input"},
    401: {"description": "Unauthorized — missing or invalid API key"},
    403: {"description": "Forbidden — invalid API key"},
    404: {"description": "Not found"},
    413: {"description": "Request too large"},
    422: {"description": "Unprocessable entity"},
    429: {"description": "Rate limit exceeded"},
    500: {"description": "Internal server error"},
}


def error_response(status_code: int, detail: str, request_id: str = "") -> JSONResponse:
    """Standardized error response."""
    body = {
        "error": {
            "code": status_code,
            "message": detail,
        }
    }
    if request_id:
        body["error"]["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
      1. Assigns a unique request ID
      2. Records timing
      3. Logs request/response summary
      4. Catches unhandled exceptions
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.client_id = request.client.host if request.client else "unknown"
        start_time = time.monotonic()

        response = await call_next(request)

        duration_ms = (time.monotonic() - start_time) * 1000

        audit = AuditEntry(
            client_id=request.state.client_id,
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        log_data = audit.to_log()
        log_data["response_size"] = response.headers.get("content-length", 0)

        if response.status_code >= 500:
            logger.error(str(log_data))
        elif response.status_code >= 400:
            logger.warning(str(log_data))
        else:
            logger.info(str(log_data))

        response.headers["X-Request-ID"] = request_id
        return response


class ExceptionHandlingMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and returns standardized errors."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            request_id = getattr(request.state, "request_id", "")
            logger.exception("Unhandled exception: %s", e)
            return error_response(500, "Internal server error", request_id)
