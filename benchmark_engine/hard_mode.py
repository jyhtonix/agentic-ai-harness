"""Hard mode controller — adaptive strategy for difficult challenges."""

from __future__ import annotations

import logging
from typing import Optional

from benchmark_engine.failure import FailureAnalyzer
from benchmark_engine.retry import RetryController
from benchmark_engine.results import BenchmarkResult

logger = logging.getLogger("benchmark_engine.hard_mode")

HARD_MODE_STRATEGIES = [
    "default",
    "change_agent_selection",
    "add_skills_context",
    "use_different_tools",
    "decompose_problem",
    "try_alternative_approach",
]


class HardModeController:
    def __init__(
        self,
        max_attempts: int = 5,
        failure_analyzer: Optional[FailureAnalyzer] = None,
        retry_controller: Optional[RetryController] = None,
    ):
        self.max_attempts = max_attempts
        self.failure_analyzer = failure_analyzer or FailureAnalyzer()
        self.retry_controller = retry_controller or RetryController(max_attempts=max_attempts)
        self._strategy_index: dict[str, int] = {}

    def get_strategy(self, challenge_id: str) -> dict:
        idx = self._strategy_index.get(challenge_id, 0)
        strategy_name = HARD_MODE_STRATEGIES[idx] if idx < len(HARD_MODE_STRATEGIES) else "fallback"

        return {
            "strategy": strategy_name,
            "attempt": idx + 1,
            "max_attempts": self.max_attempts,
            "description": self._describe(strategy_name),
        }

    def register_outcome(self, challenge_id: str, result: BenchmarkResult) -> dict:
        if result.solved:
            self._strategy_index.pop(challenge_id, None)
            return {"status": "solved", "strategy": result.status}

        idx = self._strategy_index.get(challenge_id, 0)
        self._strategy_index[challenge_id] = idx + 1

        analysis = self.failure_analyzer.analyze(result)
        self.retry_controller.register_failure(challenge_id, analysis)
        next_strategy = self.get_strategy(challenge_id)

        logger.info(
            "Hard mode attempt %d/%d for %s: %s → %s",
            idx + 1, self.max_attempts, challenge_id,
            analysis.get("category", "unknown"), next_strategy["strategy"],
        )
        return {
            "status": "failed",
            "attempt": idx + 1,
            "failure_analysis": analysis,
            "next_strategy": next_strategy,
        }

    def should_retry(self, challenge_id: str) -> bool:
        idx = self._strategy_index.get(challenge_id, 0)
        return idx < self.max_attempts

    def reset(self, challenge_id: str) -> None:
        self._strategy_index.pop(challenge_id, None)
        self.retry_controller.clear(challenge_id)

    def reset_all(self) -> None:
        self._strategy_index.clear()
        self.retry_controller.clear_all()

    @property
    def total_active(self) -> int:
        return len(self._strategy_index)

    @staticmethod
    def _describe(strategy: str) -> str:
        descriptions = {
            "default": "Standard agent pipeline with no modifications",
            "change_agent_selection": "Switch to a different specialist agent for this domain",
            "add_skills_context": "Inject additional skill context into agent prompts",
            "use_different_tools": "Try alternative tools or tool combinations",
            "decompose_problem": "Break the challenge into smaller sub-problems",
            "try_alternative_approach": "Attempt a fundamentally different solution approach",
            "fallback": "Final attempt with all available resources",
        }
        return descriptions.get(strategy, "Unknown strategy")
