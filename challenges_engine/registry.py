import logging
from typing import Optional

from challenges_engine.models import ChallengeDefinition

logger = logging.getLogger("challenges_engine.registry")


class ChallengeRegistry:
    def __init__(self):
        self._challenges: dict[str, ChallengeDefinition] = {}

    def register(self, challenge: ChallengeDefinition) -> None:
        key = challenge.name.lower().replace(" ", "-")
        self._challenges[key] = challenge
        logger.info("Registered challenge: %s (%s)", challenge.name, challenge.category)

    def register_many(self, challenges: list[ChallengeDefinition]) -> None:
        for c in challenges:
            self.register(c)

    def get(self, challenge_id: str) -> Optional[ChallengeDefinition]:
        key = challenge_id.lower().replace(" ", "-")
        return self._challenges.get(key)

    def search(
        self,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        required_skill: Optional[str] = None,
    ) -> list[ChallengeDefinition]:
        results = list(self._challenges.values())

        if category:
            cat_lower = category.lower()
            results = [c for c in results if c.category.lower() == cat_lower]

        if difficulty:
            diff_lower = difficulty.lower()
            results = [c for c in results if c.difficulty.lower() == diff_lower]

        if required_skill:
            skill_lower = required_skill.lower()
            results = [
                c for c in results
                if any(skill_lower in s.lower() for s in c.required_skills)
            ]

        return results

    def list_categories(self) -> list[str]:
        return sorted({c.category for c in self._challenges.values()})

    def __contains__(self, challenge_id: str) -> bool:
        return challenge_id.lower().replace(" ", "-") in self._challenges

    def __len__(self) -> int:
        return len(self._challenges)

    def __iter__(self):
        return iter(self._challenges.values())
