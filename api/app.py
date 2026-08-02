import logging
from typing import Optional

from fastapi import FastAPI

from api.auth import AuthProvider
from api.session_manager import SessionManager

logger = logging.getLogger("api.app")


def create_app(
    title: str = "Agentic CTF Harness API",
    version: str = "0.3.5",
    debug: bool = False,
    challenge_loader=None,
    supervisor_factory=None,
    auth_provider: Optional[AuthProvider] = None,
    session_manager: Optional[SessionManager] = None,
    memory_service=None,
) -> FastAPI:
    if auth_provider is None:
        auth_provider = AuthProvider(mode="anonymous")
    if session_manager is None:
        session_manager = SessionManager()

    app = FastAPI(
        title=title,
        version=version,
        docs_url="/docs" if debug else None,
        redoc_url="/redoc" if debug else None,
        openapi_tags=[
            {"name": "health", "description": "Health and system info"},
            {"name": "challenges", "description": "Challenge discovery and execution"},
            {"name": "sessions", "description": "Execution session management"},
            {"name": "reports", "description": "Learning report retrieval"},
        ],
    )

    app.state.auth_provider = auth_provider
    app.state.session_manager = session_manager
    app.state.challenge_loader = challenge_loader
    app.state.supervisor_factory = supervisor_factory
    app.state.memory_service = memory_service

    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    from api.routes.challenges import router as challenges_router
    from api.routes.sessions import router as sessions_router
    from api.routes.reports import router as reports_router

    app.include_router(challenges_router, prefix="/api/v1")
    app.include_router(sessions_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "version": app.version}
