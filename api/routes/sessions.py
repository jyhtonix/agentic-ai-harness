import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.schemas.execution import SessionStatusResponse
from api.auth import AuthProvider

logger = logging.getLogger("api.routes.sessions")

router = APIRouter(tags=["sessions"])


def _get_auth(request: Request) -> AuthProvider:
    return request.app.state.auth_provider


@router.get("/sessions/{session_id}")
async def get_session_status(
    request: Request,
    session_id: str,
    auth: AuthProvider = Depends(_get_auth),
):
    session_mgr = request.app.state.session_manager
    session = session_mgr.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    flag_status = None
    if session.flag_result:
        flag_status = session.flag_result.get("status", "")

    return SessionStatusResponse(
        session_id=session.session_id,
        status=session.status,
        challenge=session.challenge_id,
        flag_status=flag_status,
        error=session.error,
    )
