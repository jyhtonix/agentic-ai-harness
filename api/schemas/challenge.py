from pydantic import BaseModel, Field


class ChallengeSummary(BaseModel):
    id: str
    name: str
    category: str
    difficulty: str
    description: str = ""


class ChallengeListParams(BaseModel):
    category: str = ""
    difficulty: str = ""
    skill: str = ""


class ChallengeRunRequest(BaseModel):
    challenge_id: str = Field(..., min_length=1)
    user_prompt: str = ""


class ChallengeRunResponse(BaseModel):
    session_id: str
    status: str = "running"
