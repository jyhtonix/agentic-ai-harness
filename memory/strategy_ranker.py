"""Strategy Ranking System — ranks strategies by historical success."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from memory.strategies import StrategyMemory
from benchmark_engine.results import BenchmarkResult

logger = logging.getLogger("memory.strategy_ranker")


class StrategyRanker:
    def __init__(self, strategy_memory: Optional[StrategyMemory] = None,
                 storage_dir: Optional[str] = None):
        self.strategy_memory = strategy_memory or StrategyMemory()
        self.storage_dir = Path(storage_dir or (Path.cwd() / "memory" / "strategies"))
        self._rankings: dict[str, list[dict]] = {}
        self._load()

    def rank(self, category: str) -> list[dict]:
        strategies = self.strategy_memory.get_strategies(category)
        failed = self.strategy_memory.get_failed_approaches(category)

        scored = []
        for s in strategies:
            score = self._score_strategy(s, category, failed)
            scored.append({"strategy": s, "score": score, "status": "available"})

        scored.sort(key=lambda x: x["score"], reverse=True)

        self._rankings[category] = scored
        self._save()
        return scored

    def get_best(self, category: str) -> Optional[str]:
        ranked = self.rank(category)
        if ranked:
            return ranked[0]["strategy"]
        return None

    def get_top_n(self, category: str, n: int = 3) -> list[str]:
        ranked = self.rank(category)
        return [r["strategy"] for r in ranked[:n]]

    def record_outcome(self, category: str, strategy: str, success: bool) -> None:
        key = f"{category}:{strategy}"
        if key not in self._outcomes:
            self._outcomes[key] = {"attempts": 0, "successes": 0}
        self._outcomes[key]["attempts"] += 1
        if success:
            self._outcomes[key]["successes"] += 1
        self._save()

    def get_success_rate(self, category: str, strategy: str) -> float:
        key = f"{category}:{strategy}"
        entry = self._outcomes.get(key)
        if not entry or entry["attempts"] == 0:
            return 0.0
        return round(entry["successes"] / entry["attempts"], 3)

    def get_ranked_report(self, category: str) -> str:
        ranked = self.rank(category)
        lines = [f"Strategy Rankings for {category.title()}:", "-" * 40]
        for i, r in enumerate(ranked, 1):
            sr = self.get_success_rate(category, r["strategy"])
            lines.append(f"  {i}. {r['strategy']}")
            lines.append(f"     Score: {r['score']:.2f}  |  Success Rate: {sr:.0%}")
        return "\n".join(lines)

    def _score_strategy(self, strategy: str, category: str, failed: list[str]) -> float:
        score = self.strategy_memory._strategies.get(category, [])
        entry = next((e for e in score if e["strategy"] == strategy), None)
        base = entry["confidence"] if entry else 0.5

        if strategy in failed:
            base *= 0.3

        sr = self.get_success_rate(category, strategy)
        if sr > 0:
            base = base * 0.7 + sr * 0.3

        return round(base, 3)

    def _save(self) -> None:
        path = self.storage_dir / "rankings.json"
        with open(path, "w") as f:
            json.dump({
                "rankings": self._rankings,
                "outcomes": self._outcomes,
            }, f, indent=2)

    def _load(self) -> None:
        self._outcomes: dict[str, dict] = {}
        path = self.storage_dir / "rankings.json"
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                self._rankings = data.get("rankings", {})
                self._outcomes = data.get("outcomes", {})
            except (json.JSONDecodeError, OSError):
                self._rankings = {}
                self._outcomes = {}
