"""
FastAPI application entry point — production-ready.

Architecture:
  Request -> Middleware (auth, rate-limit, tracing, logging)
          -> Router (tasks, agents, health, metrics)
          -> Supervisor -> Agent Registry -> Specialized Agents
          -> Final response (standardized JSON envelope)

Security:
  - Bearer token authentication (configurable via API_KEY)
  - Per-client rate limiting (token bucket)
  - Input validation and prompt injection detection
  - CORS restriction
  - Request size limits

Observability:
  - Structured JSON logging
  - Per-request tracing (X-Request-ID)
  - Metrics endpoint
  - Deep health check (DB, LLM, memory)
"""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config.settings import settings
from models.llm import OpenAILLM
from agents.registry import AgentRegistry
from agents.supervisor import SupervisorAgent
from agents.researcher import ResearchAgent
from agents.coder import CodingAgent
from agents.security import SecurityAgent
from agents.qa import QAAgent
from agents.alert_analyst import AlertAnalystAgent
from agents.threat_hunter import ThreatHunterAgent
from agents.malware_analyst import MalwareAnalystAgent
from agents.incident_responder import IncidentResponderAgent
from tools.web_search import search as web_search_tool
from tools.code_runner import run as code_runner_tool

from core.security import (
    security_scheme,
    authenticate_request,
    check_rate_limit,
    validate_input,
    sanitize_output,
    get_cors_origins,
    load_api_keys,
)
from core.middleware import (
    RequestLoggingMiddleware,
    ExceptionHandlingMiddleware,
    error_response,
    configure_logging,
)
from core.monitoring import (
    check_health,
    metrics,
    METRIC_API_REQUESTS,
    METRIC_DURATION,
)
from core.cache import llm_cache

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

configure_logging(json_output=not settings.debug)
logger = logging.getLogger("api")

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Agent Harness API v%s", "0.3.0")
    load_api_keys()
    logger.info(
        "API keys loaded: %d hash(es), auth=%s",
        len({k for k in [settings.api_key] if k}),
        "enabled" if settings.api_key else "disabled",
    )

    if settings.database_url and "postgresql" in settings.database_url:
        from database.connection import init_database
        await init_database()
        logger.info("Database initialized")

    yield

    if settings.database_url and "postgresql" in settings.database_url:
        from database.connection import close_database
        await close_database()
        logger.info("Database connection closed")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Agent Harness — Multi-Agent System",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_tags=[
        {"name": "tasks", "description": "Agent task execution"},
        {"name": "agents", "description": "Agent registry"},
        {"name": "system", "description": "Health, metrics, and system info"},
    ],
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

cors_origins = get_cors_origins()
if cors_origins:
    logger.info("CORS origins: %s", cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(ExceptionHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Request size limits
# ---------------------------------------------------------------------------

app.max_request_size = 1024 * 1024  # 1 MB


# ---------------------------------------------------------------------------
# Dependency wiring
# ---------------------------------------------------------------------------

llm = OpenAILLM()

registry = AgentRegistry()
registry.register(ResearchAgent(llm, web_search_tool=web_search_tool))
registry.register(CodingAgent(llm, code_runner_tool=code_runner_tool))
registry.register(SecurityAgent(llm))
registry.register(QAAgent(llm))
registry.register(AlertAnalystAgent(llm))
registry.register(ThreatHunterAgent(llm))
registry.register(MalwareAnalystAgent(llm))
registry.register(IncidentResponderAgent(llm))

supervisor = SupervisorAgent(llm, registry)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

async def auth_dependency(request: Request) -> str:
    """Authenticate and rate-limit the request."""
    credentials = await security_scheme(request)
    client_id = await authenticate_request(credentials)
    request.state.client_id = client_id
    await check_rate_limit(request)
    return client_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TaskRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=100_000)


class TaskResponse(BaseModel):
    task_id: str
    request: str
    analysis: str
    agent_results: list[dict]
    final_response: str


class ErrorResponse(BaseModel):
    error: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    tags=["system"],
    summary="Deep health check",
    description="Returns system health including database, LLM, and memory status",
)
async def health():
    """Deep health check across all system dependencies."""
    status = await check_health(
        llm=llm,
        memory_manager=None,
    )
    status_code = 200 if status.healthy else 503
    content = {
        "status": "ok" if status.healthy else "degraded",
        "version": status.version,
        "checks": status.checks,
        "metrics": metrics.snapshot(),
    }
    return JSONResponse(content=content, status_code=status_code)


@app.get(
    "/metrics",
    tags=["system"],
    summary="System metrics",
    description="Request counts, LLM usage, cache stats, and error rates",
)
async def get_metrics():
    """Return system metrics and cache statistics."""
    return {
        "metrics": metrics.snapshot(),
        "cache": llm_cache.stats(),
        "agents": registry.list_agents(),
    }


@app.get(
    "/api/v1/agents",
    tags=["agents"],
    summary="List registered agents",
    description="Returns all specialized agents registered with the Supervisor",
)
async def list_agents(client_id: str = Depends(auth_dependency)):
    """List all registered specialized agents."""
    return {"agents": registry.list_agents()}


@app.post(
    "/api/v1/tasks",
    response_model=TaskResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
    tags=["tasks"],
    summary="Execute a task",
    description="Submit a natural-language request to the multi-agent system",
)
async def create_task(
    req: TaskRequest,
    request: Request,
    client_id: str = Depends(auth_dependency),
):
    """Submit a request to the multi-agent system via the Supervisor."""
    start_time = time.monotonic()
    metrics.increment(METRIC_API_REQUESTS, {"endpoint": "create_task"})

    safe_input = validate_input(req.input)

    result = await supervisor.run(safe_input)

    duration = time.monotonic() - start_time
    metrics.increment(METRIC_DURATION)

    sanitized = sanitize_output(result.get("final_response", ""))

    logger.info(
        "Task complete | client=%.12s duration=%.2fs agents=%d tokens_estimate=%d",
        client_id, duration,
        len(result.get("agent_results", [])),
        len(sanitized) // 4,
    )

    return TaskResponse(
        task_id=str(uuid.uuid4()),
        request=result["request"],
        analysis=result.get("analysis", ""),
        agent_results=result.get("agent_results", []),
        final_response=sanitized,
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.exception_handler(413)
async def request_entity_too_large(request: Request, exc: Exception):
    return error_response(413, "Request body too large")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return error_response(exc.status_code, exc.detail)
