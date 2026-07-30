import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from api.schemas.session import SessionState

logger = logging.getLogger("api.session_manager")


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, SessionState] = {}

    def create_session(self, challenge_id: str, user_prompt: str = "") -> SessionState:
        session_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        state = SessionState(
            session_id=session_id,
            challenge_id=challenge_id,
            user_prompt=user_prompt,
            status="CREATED",
            created_time=now,
        )
        self._sessions[session_id] = state
        logger.info("Session created: %s for challenge '%s'", session_id, challenge_id)
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def update_status(self, session_id: str, status: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.status = status

    def set_result(self, session_id: str, result: dict) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.result = result
            session.completed_time = datetime.now(timezone.utc).isoformat()

    def set_flag_result(self, session_id: str, flag_result: dict) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.flag_result = flag_result

    def set_learning_report(self, session_id: str, report: dict) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.learning_report = report

    def set_error(self, session_id: str, error: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.error = error
            session.status = "FAILED"
            session.completed_time = datetime.now(timezone.utc).isoformat()

    def list_sessions(self) -> list[SessionState]:
        return list(self._sessions.values())

    def __contains__(self, session_id: str) -> bool:
        return session_id in self._sessions
