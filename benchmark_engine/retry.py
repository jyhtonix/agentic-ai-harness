from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("benchmark_engine.retry")

RETRY_STRATEGIES = {
    "missing_skill": "Add relevant skill context and retry with enriched prompt",
    "wrong_agent": "Switch to a different specialist agent for this challenge type",
    "insufficient_reasoning": "Increase temperature and add chain-of-thought prompting",
    "missing_tool": "Allow missing tool or use alternative approach",
    "verification_failure": "Double-check expected flag and verification method",
    "timeout": "Reduce complexity or increase timeout limit",
    "runtime_error": "Fix runtime dependencies and retry",
    "unknown": "Generic retry with alternative approach",
}

STRATEGY_PENALTIES = {
    "missing_skill": 0.05,
    "wrong_agent": 0.10,
    "insufficient_reasoning": 0.02,
    "missing_tool": 0.08,
    "verification_failure": 0.0,
    "timeout": 0.15,
    "runtime_error": 0.20,
    "unknown": 0.05,
}


class RetryController:
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self._failures: dict[str, list[dict]] = {}

    def register_failure(self, challenge_id: str, analysis: dict) -> None:
        if challenge_id not in self._failures:
            self._failures[challenge_id] = []
        self._failures[challenge_id].append(analysis)
        logger.debug("Registered failure for %s: %s", challenge_id, analysis.get("category", "unknown"))

    def get_strategy(self, challenge_id: str, attempt: int) -> dict:
        failures = self._failures.get(challenge_id, [])
        if not failures:
            return {"action": "initial_attempt", "strategy": "default"}

        last_failure = failures[-1]
        category = last_failure.get("category", "unknown")
        strategy_text = RETRY_STRATEGIES.get(category, "Generic retry")
        penalty = sum(STRATEGY_PENALTIES.get(f.get("category", "unknown"), 0.05) for f in failures)

        return {
            "action": "retry",
            "attempt": attempt,
            "category": category,
            "strategy": strategy_text,
            "penalty": round(penalty, 3),
            "recommendation": last_failure.get("recommendation", ""),
        }

    def exceeded(self, challenge_id: str, attempt: int) -> bool:
        return attempt >= self.max_attempts

    def clear(self, challenge_id: str) -> None:
        self._failures.pop(challenge_id, None)

    def clear_all(self) -> None:
        self._failures.clear()

    @property
    def total_failures(self) -> int:
        return sum(len(v) for v in self._failures.values())
