"""KnowledgeUpdater — updates memory and knowledge stores after learning."""

from __future__ import annotations

import logging
from typing import Optional

from memory.strategies import StrategyMemory
from memory.failures import FailureMemory
from memory.solutions import SolutionMemory
from skills_engine.improvement import SkillImprovementProposal

logger = logging.getLogger("learning_engine.updater")


class KnowledgeUpdater:
    def __init__(
        self,
        strategy_memory: Optional[StrategyMemory] = None,
        failure_memory: Optional[FailureMemory] = None,
        solution_memory: Optional[SolutionMemory] = None,
        skill_proposer: Optional[SkillImprovementProposal] = None,
    ):
        self.strategy_memory = strategy_memory or StrategyMemory()
        self.failure_memory = failure_memory or FailureMemory()
        self.solution_memory = solution_memory or SolutionMemory()
        self.skill_proposer = skill_proposer or SkillImprovementProposal()
        self._updates: list[dict] = []

    def update_from_learning(self, learning_entry: dict) -> dict:
        updates = []
        challenge_id = learning_entry.get("challenge_id", "unknown")
        category = learning_entry.get("category", "unknown")

        if learning_entry.get("status") == "solved":
            updates.append("solution_memory_updated")

        if learning_entry.get("actions_taken"):
            if "detected_skill_gaps" in learning_entry.get("actions_taken", []):
                skill_gaps = learning_entry.get("skill_gaps", {})
                for gap in skill_gaps.get("gaps", []):
                    proposal = self.skill_proposer.generate(
                        gap, category, skill_gaps.get("confidence", 0.5)
                    )
                    updates.append(f"skill_proposal: {proposal['proposed_skill_name']}")

            if "evolved_strategy" in learning_entry.get("actions_taken", []):
                evolved = learning_entry.get("evolved_strategy", [])
                for strategy in evolved:
                    self.strategy_memory.record(category, strategy, confidence=0.6)
                updates.append("strategy_memory_evolved")

        entry = {
            "challenge_id": challenge_id,
            "updates": updates,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
        self._updates.append(entry)
        return entry

    def get_update_history(self) -> list[dict]:
        return list(self._updates)

    def get_skill_proposals(self) -> list[dict]:
        return self.skill_proposer.get_all_proposals()

    def clear(self) -> None:
        self._updates.clear()
        self.skill_proposer.clear()
