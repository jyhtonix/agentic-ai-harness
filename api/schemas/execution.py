from typing import Optional

from pydantic import BaseModel


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    challenge: str = ""
    flag_status: Optional[str] = None
    error: Optional[str] = None
