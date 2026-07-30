from typing import Optional

from pydantic import BaseModel


class ReportResponse(BaseModel):
    session_id: str
    challenge: str = ""
    challenge_category: str = ""
    challenge_difficulty: str = ""
    skills_used: list[dict] = []
    tools_used: list[str] = []
    flag_result: str = ""
    flag_method: str = ""
    verification_status: str = ""
    confidence_score: float = 0.0
    difficulty_estimate: str = ""
    recommendations: list[str] = []
    student_report: str = ""
    instructor_summary: str = ""
    error: Optional[str] = None
