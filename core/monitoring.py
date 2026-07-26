"""
Monitoring module — health checks, metrics, and system diagnostics.

Provides:
  - Deep health check (database, LLM, memory)
  - Prometheus-style metrics
  - Startup dependency validation
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("core.monitoring")


# ---------------------------------------------------------------------------
# Metrics collector
# ---------------------------------------------------------------------------

@dataclass
class Metric:
    """A single metric value with optional labels."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """
    In-memory metrics collector. Can be extended to push to
    Prometheus, Datadog, or OpenTelemetry.
    """

    def __init__(self):
        self._metrics: list[Metric] = []
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}

    def increment(self, name: str, labels: Optional[dict[str, str]] = None) -> None:
        key = f"{name}_{labels}" if labels else name
        self._counters[key] = self._counters.get(key, 0) + 1
        self._metrics.append(Metric(name=name, value=1, labels=labels or {}))

    def gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value
        self._metrics.append(Metric(name=name, value=value))

    def get_counter(self, name: str, labels: Optional[dict[str, str]] = None) -> float:
        key = f"{name}_{labels}" if labels else name
        return self._counters.get(key, 0.0)

    def get_gauge(self, name: str) -> Optional[float]:
        return self._gauges.get(name)

    def snapshot(self) -> dict:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }


metrics = MetricsCollector()


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

@dataclass
class HealthStatus:
    healthy: bool
    checks: dict[str, dict] = field(default_factory=dict)
    version: str = "0.3.0"


async def check_health(
    db_session_factory=None,
    llm=None,
    memory_manager=None,
) -> HealthStatus:
    """
    Deep health check. Tests database connectivity, LLM availability,
    and memory system health. Returns a structured status object.
    """
    status = HealthStatus(healthy=True)

    # Database check
    if db_session_factory:
        try:
            async with db_session_factory() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
            status.checks["database"] = {"status": "ok"}
        except Exception as e:
            status.healthy = False
            status.checks["database"] = {"status": "error", "detail": str(e)}
    else:
        status.checks["database"] = {"status": "not_configured"}

    # LLM check
    if llm:
        try:
            resp = await llm.chat(
                [{"role": "user", "content": "Respond with just: ok"}],
                max_tokens=10,
                temperature=0,
            )
            status.checks["llm"] = {
                "status": "ok",
                "model": getattr(llm, "model", "unknown"),
            }
        except Exception as e:
            status.healthy = False
            status.checks["llm"] = {"status": "error", "detail": str(e)}
    else:
        status.checks["llm"] = {"status": "not_configured"}

    # Memory check
    if memory_manager:
        try:
            working_snap = memory_manager.working.snapshot()
            status.checks["memory"] = {
                "status": "ok",
                "working_task": working_snap.get("current_task", "")[:50] or "idle",
                "vector_entries": memory_manager.vector.count() if memory_manager.vector else 0,
            }
        except Exception as e:
            status.checks["memory"] = {"status": "error", "detail": str(e)}
    else:
        status.checks["memory"] = {"status": "not_configured"}

    # Token usage summary
    token_total = metrics.get_counter("llm_tokens_total")
    status.checks["usage"] = {
        "total_requests": int(metrics.get_counter("api_requests_total")),
        "total_llm_calls": int(metrics.get_counter("llm_calls_total")),
        "total_tokens": int(token_total),
    }

    return status


# ---------------------------------------------------------------------------
# Metric labels for consistency
# ---------------------------------------------------------------------------

METRIC_API_REQUESTS = "api_requests_total"
METRIC_LLM_CALLS = "llm_calls_total"
METRIC_LLM_TOKENS = "llm_tokens_total"
METRIC_ERRORS = "errors_total"
METRIC_TOOL_CALLS = "tool_calls_total"
METRIC_DURATION = "request_duration_seconds"
