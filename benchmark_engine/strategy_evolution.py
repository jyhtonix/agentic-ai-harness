"""Strategy Evolution Engine — improves strategies based on historical results."""

from __future__ import annotations

import logging
from typing import Optional

from memory.strategies import StrategyMemory
from benchmark_engine.results import BenchmarkResult

logger = logging.getLogger("benchmark_engine.strategy_evolution")


class StrategyEvolutionEngine:
    def __init__(self, strategy_memory: Optional[StrategyMemory] = None):
        self.strategy_memory = strategy_memory or StrategyMemory()

    def evolve(self, category: str, results: list[BenchmarkResult]) -> list[str]:
        if not results:
            return [f"Apply standard {category} methodology"]

        solved = [r for r in results if r.solved]
        failed = [r for r in results if not r.solved]

        evolved = []

        if solved:
            evolved.extend(self._learn_from_successes(category, solved))

        if failed:
            evolved.extend(self._learn_from_failures(category, failed))

        if not evolved:
            evolved = [f"Apply standard {category} analysis methodology"]

        return evolved

    def evolve_strategy_text(self, category: str, results: list[BenchmarkResult]) -> str:
        steps = self.evolve(category, results)
        lines = [f"{category.title()} Analysis Strategy:"]
        for i, step in enumerate(steps, 1):
            lines.append(f"  {i}. {step}")
        return "\n".join(lines)

    def _learn_from_successes(self, category: str, solved: list[BenchmarkResult]) -> list[str]:
        steps = []
        for r in solved:
            strategy_key = f"{category}:{'/'.join(r.tools_used)}:{'/'.join(r.agents_used)}"
            self.strategy_memory.record(category, strategy_key, confidence=r.confidence)

        common_tools = self._find_common(list(r.tools_used for r in solved))
        common_agents = self._find_common(list(r.agents_used for r in solved))

        if common_tools:
            steps.append(f"Use tools: {', '.join(common_tools[:3])}")
        if common_agents:
            steps.append(f"Deploy agents: {', '.join(common_agents[:3])}")
        steps.append("Validate output and verify flag format")

        return steps

    def _learn_from_failures(self, category: str, failed: list[BenchmarkResult]) -> list[str]:
        steps = []
        for r in failed:
            self.strategy_memory.record_failed(
                category,
                f"{category}:{'/'.join(r.tools_used)}:{'/'.join(r.agents_used)}",
                r.failure_reason or "Unknown",
            )

        failure_types = {}
        for r in failed:
            ft = r.failure_category or "unknown"
            failure_types[ft] = failure_types.get(ft, 0) + 1

        if failure_types:
            top = max(failure_types.items(), key=lambda x: x[1])
            steps.append(f"Avoid previous failure pattern: {top[0]} ({top[1]} occurrences)")

        missing_skills = [r.failure_reason for r in failed
                          if r.failure_category == "missing_skill" and r.failure_reason]
        if missing_skills:
            steps.append(f"Address skill gaps: {', '.join(missing_skills[:3])}")

        steps.append("Consider alternative approach if standard methods fail")

        return steps

    @staticmethod
    def _find_common(lists: list[list[str]]) -> list[str]:
        counts: dict[str, int] = {}
        total = len(lists)
        for l in lists:
            for item in l:
                counts[item] = counts.get(item, 0) + 1
        return sorted([item for item, count in counts.items() if count / max(total, 1) >= 0.3],
                      key=lambda x: counts[x], reverse=True)
