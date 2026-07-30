from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SessionState(BaseModel):
    session_id: str
    challenge_id: str
    user_prompt: str = ""
    status: str = "CREATED"
    created_time: str = ""
    completed_time: Optional[str] = None
    result: Optional[dict] = None
    flag_result: Optional[dict] = None
    learning_report: Optional[dict] = None
    error: Optional[str] = None
