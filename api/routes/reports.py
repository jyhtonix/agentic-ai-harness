import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.schemas.report import ReportResponse
from api.auth import AuthProvider

logger = logging.getLogger("api.routes.reports")

router = APIRouter(tags=["reports"])


def _get_auth(request: Request) -> AuthProvider:
    return request.app.state.auth_provider


@router.get("/reports/{session_id}")
async def get_report(
    request: Request,
    session_id: str,
    auth: AuthProvider = Depends(_get_auth),
):
    session_mgr = request.app.state.session_manager
    session = session_mgr.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    if session.status not in ("COMPLETED", "FAILED"):
        raise HTTPException(status_code=400, detail=f"Session '{session_id}' is {session.status}, not yet complete")

    lr = session.learning_report or {}
    result = session.result or {}

    challenge_info = result.get("challenge", {})
    flag_ver = session.flag_result or {}

    return ReportResponse(
        session_id=session_id,
        challenge=session.challenge_id,
        challenge_category=challenge_info.get("category", ""),
        challenge_difficulty=challenge_info.get("difficulty", ""),
        skills_used=lr.get("skills_used", []),
        flag_result=flag_ver.get("status", ""),
        flag_method=flag_ver.get("method", ""),
        verification_status=lr.get("verification_result", {}).get("status", ""),
        confidence_score=lr.get("verification_result", {}).get("confidence_score", 0.0),
        difficulty_estimate=lr.get("difficulty_estimate", ""),
        recommendations=lr.get("recommendations", []),
        student_report=lr.get("student_report", ""),
        instructor_summary=lr.get("instructor_summary", ""),
        error=session.error,
    )
