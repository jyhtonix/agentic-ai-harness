from __future__ import annotations

import logging
from typing import Optional

from benchmark_engine.results import BenchmarkResult

logger = logging.getLogger("benchmark_engine.failure")

FAILURE_CATEGORIES = {
    "missing_skill": ["missing skill", "no matching skill", "skill not found",
                      "insufficient skill", "skill gap", "unknown technique"],
    "wrong_agent": ["wrong agent", "incorrect agent", "agent not suited",
                    "agent mismatch", "wrong specialist", "incorrect approach"],
    "insufficient_reasoning": ["insufficient reasoning", "incorrect analysis",
                               "wrong conclusion", "misunderstood", "misinterpreted",
                               "incomplete analysis", "reasoning error"],
    "missing_tool": ["tool not found", "missing tool", "tool unavailable",
                     "tool error", "command not found", "execution failed"],
    "verification_failure": ["PASS", "flag mismatch", "wrong flag",
                             "verification failed", "incorrect flag", "no flag"],
    "timeout": ["timeout", "timed out", "too slow", "took too long"],
    "not_found": ["not found", "file not found", "challenge not found", "unavailable"],
    "runtime_error": ["error", "exception", "crash", "failed", "unexpected error"],
}

FAILURE_CATEGORY_WEIGHTS = {
    "missing_skill": 0.8,
    "wrong_agent": 0.7,
    "insufficient_reasoning": 0.6,
    "missing_tool": 0.5,
    "verification_failure": 0.4,
    "timeout": 0.3,
    "runtime_error": 0.9,
}


class FailureAnalyzer:
    def analyze(self, result: BenchmarkResult) -> dict:
        if result.solved:
            return {"category": None, "reason": "solved", "recommendation": "none_needed"}

        reason = result.failure_reason or ""
        flag_status = (result.flag_result or "").lower()
        text = (reason + " " + flag_status).lower()

        best_category = "unknown"
        best_score = 0

        for category, keywords in FAILURE_CATEGORIES.items():
            score = sum(2.0 if kw in text else 0.0 for kw in keywords)
            if score > best_score:
                best_score = score
                best_category = category

        if best_score == 0 and result.status == "timeout":
            best_category = "timeout"
        if best_score == 0 and result.status == "error":
            best_category = "runtime_error"

        return {
            "category": best_category,
            "reason": reason or "No failure reason recorded",
            "recommendation": self._get_recommendation(best_category, result),
            "confidence_weight": FAILURE_CATEGORY_WEIGHTS.get(best_category, 0.5),
        }

    def classify(self, result: BenchmarkResult) -> str:
        analysis = self.analyze(result)
        return analysis.get("category", "unknown")

    @staticmethod
    def _get_recommendation(category: str, result: BenchmarkResult) -> str:
        recs = {
            "missing_skill": (
                f"Add skills for {result.category} challenges. "
                f"Review skill registry for gaps in {result.difficulty} difficulty."
            ),
            "wrong_agent": (
                "Review agent selection logic. The coordinator chose a suboptimal "
                "agent for this challenge type."
            ),
            "insufficient_reasoning": (
                "Agent reasoning quality needs improvement. Consider adding more "
                "domain-specific context or chain-of-thought prompting."
            ),
            "missing_tool": (
                f"Required tool not available for {result.category} challenge. "
                "Check tool registry and execution policy."
            ),
            "verification_failure": (
                "Flag format or content mismatch. Verify expected flag and "
                "verification method."
            ),
            "timeout": (
                "Challenge timed out. Consider increasing timeout or optimizing "
                "agent execution pipeline."
            ),
            "not_found": "Challenge or dataset not found. Verify challenge exists in loader path.",
            "runtime_error": "Unexpected runtime error. Check logs for exception details.",
        }
        return recs.get(category, f"Review {result.category} challenge analysis pipeline.")
