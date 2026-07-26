"""
Security module — authentication, authorization, API key management.

Provides:
  - API key authentication (Bearer token)
  - Rate limiting (token bucket per client)
  - Input validation and sanitization
  - Audit logging helpers
"""

import hashlib
import hmac
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.settings import settings

logger = logging.getLogger("core.security")

security_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# API Key authentication
# ---------------------------------------------------------------------------

API_KEY_HASHES: set[str] = set()


def load_api_keys(*, keys: Optional[list[str]] = None) -> None:
    """Load accepted API keys (stored as SHA-256 hashes)."""
    if keys:
        for k in keys:
            API_KEY_HASHES.add(hashlib.sha256(k.encode()).hexdigest())
    env_key = settings.api_key
    if env_key:
        API_KEY_HASHES.add(hashlib.sha256(env_key.encode()).hexdigest())


def validate_api_key(token: str) -> bool:
    """Constant-time comparison against stored key hashes."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    for stored_hash in API_KEY_HASHES:
        if hmac.compare_digest(token_hash, stored_hash):
            return True
    return False


async def authenticate_request(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> str:
    """
    Authenticate a request. Returns the token on success,
    raises HTTPException on failure.
    """
    if not settings.api_key and not API_KEY_HASHES:
        logger.warning("No API keys configured — authentication disabled")
        return "anonymous"

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme. Use Bearer token.",
        )

    if not validate_api_key(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return credentials.credentials


# ---------------------------------------------------------------------------
# Rate limiting (sliding window token bucket)
# ---------------------------------------------------------------------------

@dataclass
class Bucket:
    tokens: float
    last_refill: float


class RateLimiter:
    """
    Per-client token bucket rate limiter.

    Each client (identified by token hash or IP) gets a bucket that
    refills at `rate` tokens per second, up to `capacity`.
    """

    def __init__(self, rate: float = 10.0, capacity: float = 20.0):
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, Bucket] = {}

    def check(self, client_id: str) -> bool:
        """Check if a request is allowed. Returns True if allowed."""
        now = time.monotonic()
        bucket = self._buckets.get(client_id)

        if bucket is None:
            self._buckets[client_id] = Bucket(tokens=self.capacity - 1, last_refill=now)
            return True

        elapsed = now - bucket.last_refill
        bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.rate)
        bucket.last_refill = now

        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return True

        return False

    def reset(self, client_id: str) -> None:
        self._buckets.pop(client_id, None)


rate_limiter = RateLimiter(
    rate=settings.rate_limit_requests,
    capacity=settings.rate_limit_burst,
)


async def check_rate_limit(request: Request) -> None:
    """FastAPI dependency that checks rate limits."""
    client_id = request.state.client_id if hasattr(request.state, "client_id") else request.client.host
    if not rate_limiter.check(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
        )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

MAX_INPUT_LENGTH = 100_000
MAX_OUTPUT_LENGTH = 500_000
BLOCKED_PATTERNS = [
    re.compile(r"system\s*:\s*ignore\s+all\s+previous", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|not\s+bound|free)", re.IGNORECASE),
]


def validate_input(text: str) -> str:
    """
    Validate and sanitize user input.
    Raises HTTPException if input is suspicious.
    """
    stripped = text.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="Input cannot be empty")

    if len(stripped) > MAX_INPUT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Input exceeds maximum length of {MAX_INPUT_LENGTH} characters",
        )

    for pattern in BLOCKED_PATTERNS:
        if pattern.search(stripped):
            raise HTTPException(
                status_code=400,
                detail="Input contains disallowed patterns",
            )

    return stripped


def sanitize_output(text: str) -> str:
    """Truncate and sanitize LLM output."""
    if len(text) > MAX_OUTPUT_LENGTH:
        text = text[:MAX_OUTPUT_LENGTH] + "\n\n[Output truncated]"
    return text


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def get_cors_origins() -> list[str]:
    """Return configured CORS origins."""
    origins = settings.cors_origins
    if origins and origins != ["*"]:
        return origins
    if settings.debug:
        return ["*"]
    return []


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    client_id: str
    method: str
    path: str
    status_code: int
    duration_ms: float
    request_id: str
    error: Optional[str] = None

    def to_log(self) -> dict:
        return {
            "event": "api_request",
            "client_id": self.client_id[:12] + "..." if len(self.client_id) > 16 else self.client_id,
            "method": self.method,
            "path": self.path,
            "status": self.status_code,
            "duration_ms": round(self.duration_ms, 1),
            "request_id": self.request_id,
            "error": self.error,
        }
