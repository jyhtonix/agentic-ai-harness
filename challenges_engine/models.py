from __future__ import annotations

from pydantic import BaseModel, Field


class ChallengeDefinition(BaseModel):
    name: str
    category: str
    difficulty: str
    description: str
    challenge_dir: str = ""
    required_skills: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    verification: dict = Field(default_factory=lambda: {"type": "exact_flag"})
    flag_format: str = ""
    expected_flag: str = ""
    hints: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)

    def is_beginner(self) -> bool:
        return self.difficulty == "beginner"

    def __repr__(self):
        return f"ChallengeDefinition(name='{self.name}', category='{self.category}', difficulty='{self.difficulty}')"
