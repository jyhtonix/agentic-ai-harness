import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.schemas.challenge import ChallengeRunRequest, ChallengeRunResponse, ChallengeSummary
from api.auth import AuthProvider

logger = logging.getLogger("api.routes.challenges")

router = APIRouter(tags=["challenges"])


def _get_auth(request: Request) -> AuthProvider:
    return request.app.state.auth_provider


@router.get("/challenges")
async def list_challenges(
    request: Request,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    skill: Optional[str] = None,
    auth: AuthProvider = Depends(_get_auth),
):
    loader = request.app.state.challenge_loader
    if not loader:
        raise HTTPException(status_code=503, detail="Challenge system not available")

    all_challenges = loader.load_all()
    results = []
    for c in all_challenges:
        if category and c.category != category:
            continue
        if difficulty and c.difficulty != difficulty:
            continue
        if skill and not any(skill.lower() in s.lower() for s in c.required_skills):
            continue
        results.append(ChallengeSummary(
            id=c.name.lower().replace(" ", "-"),
            name=c.name,
            category=c.category,
            difficulty=c.difficulty,
            description=c.description,
        ))

    return results


@router.post("/challenges/run", status_code=201)
async def run_challenge(
    request: Request,
    body: ChallengeRunRequest,
    auth: AuthProvider = Depends(_get_auth),
):
    loader = request.app.state.challenge_loader
    session_mgr = request.app.state.session_manager
    supervisor_factory = request.app.state.supervisor_factory

    if not loader:
        raise HTTPException(status_code=503, detail="Challenge system not available")
    if not supervisor_factory:
        raise HTTPException(status_code=503, detail="Supervisor system not available")

    challenge = loader.load(body.challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail=f"Challenge '{body.challenge_id}' not found")

    session = session_mgr.create_session(body.challenge_id, body.user_prompt)

    async def _run():
        try:
            session_mgr.update_status(session.session_id, "RUNNING")
            supervisor = supervisor_factory()
            user_prompt = body.user_prompt or challenge.description
            result = await supervisor.run(user_prompt, challenge_id=body.challenge_id)
            session_mgr.set_result(session.session_id, result)
            flag_ver = result.get("flag_verification")
            if flag_ver:
                session_mgr.set_flag_result(session.session_id, flag_ver)
            lr = result.get("learning_report")
            if lr:
                session_mgr.set_learning_report(session.session_id, lr)
            session_mgr.update_status(session.session_id, "COMPLETED")
            logger.info("Session %s completed successfully", session.session_id)
            _capture_learning(request, result)
        except Exception as e:
            logger.error("Session %s failed: %s", session.session_id, e)
            session_mgr.set_error(session.session_id, str(e))

    asyncio.create_task(_run())

    return ChallengeRunResponse(session_id=session.session_id, status="running")


def _capture_learning(request: Request, supervisor_result: dict) -> None:
    """Feed a completed challenge run into the CTF learning loop."""
    memory_service = request.app.state.memory_service
    if not memory_service:
        return
    try:
        memory_service.record_supervisor_output(supervisor_result)
    except Exception as e:
        logger.warning("Learning capture failed: %s", e)
