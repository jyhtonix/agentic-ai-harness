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

ENHANCED_RETRY_PHASES = [
    "normal_execution",
    "change_strategy",
    "change_agent_assignment",
    "agent_debate",
    "generate_new_hypothesis",
    "execute_improved_plan",
]

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
    def __init__(self, max_attempts: int = 3, use_enhanced: bool = False):
        self.max_attempts = max_attempts
        self.use_enhanced = use_enhanced
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

        if self.use_enhanced:
            return self._get_enhanced_strategy(challenge_id, attempt, failures)

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

    def _get_enhanced_strategy(self, challenge_id: str, attempt: int,
                                failures: list[dict]) -> dict:
        phase_idx = min(attempt - 1, len(ENHANCED_RETRY_PHASES) - 1)
        phase = ENHANCED_RETRY_PHASES[phase_idx]

        last_failure = failures[-1]
        category = last_failure.get("category", "unknown")

        phase_descriptions = {
            "normal_execution": "Standard agent pipeline execution",
            "change_strategy": "Failure detected. Switching to alternative strategy based on analysis.",
            "change_agent_assignment": "Reassigning to different specialist agent for this domain.",
            "agent_debate": "Initiating agent debate to resolve conflicting approaches.",
            "generate_new_hypothesis": "Generating new hypothesis based on accumulated failure data.",
            "execute_improved_plan": "Executing improved plan incorporating all previous learnings.",
        }

        return {
            "action": "retry",
            "attempt": attempt,
            "phase": phase,
            "phase_description": phase_descriptions.get(phase, "Retrying with adjustments"),
            "category": category,
            "strategy": RETRY_STRATEGIES.get(category, "Enhanced retry with strategy change"),
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
