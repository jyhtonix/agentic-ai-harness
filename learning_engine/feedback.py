"""FeedbackCollector — gathers and processes feedback from challenge attempts."""

from __future__ import annotations

import logging
from typing import Optional

from benchmark_engine.results import BenchmarkResult

logger = logging.getLogger("learning_engine.feedback")


class FeedbackCollector:
    def __init__(self):
        self._feedback: list[dict] = []

    def collect(self, result: BenchmarkResult, notes: str = "") -> dict:
        entry = {
            "challenge_id": result.challenge_id,
            "category": result.category,
            "difficulty": result.difficulty,
            "status": result.status,
            "execution_time": result.execution_time,
            "confidence": result.confidence,
            "notes": notes,
            "solved": result.solved,
        }
        self._feedback.append(entry)
        return entry

    def get_feedback(self, category: Optional[str] = None,
                     status: Optional[str] = None) -> list[dict]:
        results = list(self._feedback)
        if category:
            results = [f for f in results if f.get("category") == category]
        if status:
            results = [f for f in results if f.get("status") == status]
        return results

    def get_summary(self) -> dict:
        if not self._feedback:
            return {"total": 0, "solved": 0, "categories": {}}
        solved = sum(1 for f in self._feedback if f.get("solved"))
        categories: dict[str, dict] = {}
        for f in self._feedback:
            cat = f.get("category", "unknown")
            if cat not in categories:
                categories[cat] = {"total": 0, "solved": 0}
            categories[cat]["total"] += 1
            if f.get("solved"):
                categories[cat]["solved"] += 1
        return {
            "total": len(self._feedback),
            "solved": solved,
            "success_rate": round(solved / len(self._feedback), 3) if self._feedback else 0,
            "categories": categories,
        }

    def clear(self) -> None:
        self._feedback.clear()
