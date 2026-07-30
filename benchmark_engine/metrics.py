from __future__ import annotations

import time
from typing import Optional

from benchmark_engine.results import BenchmarkResult


class MetricsCollector:
    def __init__(self):
        self._results: list[BenchmarkResult] = []
        self._start_time: Optional[float] = None

    def start_timer(self) -> None:
        self._start_time = time.time()

    def elapsed(self) -> float:
        if self._start_time is None:
            return 0.0
        return round(time.time() - self._start_time, 3)

    def record(self, result: BenchmarkResult) -> None:
        self._results.append(result)

    def record_many(self, results: list[BenchmarkResult]) -> None:
        self._results.extend(results)

    @property
    def total(self) -> int:
        return len(self._results)

    @property
    def solved(self) -> int:
        return sum(1 for r in self._results if r.solved)

    @property
    def failed(self) -> int:
        return sum(1 for r in self._results if r.failed)

    @property
    def partial(self) -> int:
        return sum(1 for r in self._results if r.status == "partial")

    @property
    def success_rate(self) -> float:
        if not self._results:
            return 0.0
        return self.solved / len(self._results)

    @property
    def average_confidence(self) -> float:
        values = [r.confidence for r in self._results if r.confidence > 0]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)

    @property
    def total_execution_time(self) -> float:
        return round(sum(r.execution_time for r in self._results), 2)

    def by_category(self) -> dict[str, dict]:
        cats: dict[str, dict] = {}
        for r in self._results:
            cat = r.category or "unknown"
            if cat not in cats:
                cats[cat] = {"total": 0, "solved": 0, "failed": 0, "success_rate": 0.0}
            cats[cat]["total"] += 1
            if r.solved:
                cats[cat]["solved"] += 1
            if r.failed:
                cats[cat]["failed"] += 1
        for cat in cats:
            t = cats[cat]["total"]
            cats[cat]["success_rate"] = round(cats[cat]["solved"] / t, 3) if t else 0.0
        return cats

    def by_difficulty(self) -> dict[str, dict]:
        diffs: dict[str, dict] = {}
        for r in self._results:
            d = r.difficulty or "unknown"
            if d not in diffs:
                diffs[d] = {"total": 0, "solved": 0, "failed": 0, "success_rate": 0.0}
            diffs[d]["total"] += 1
            if r.solved:
                diffs[d]["solved"] += 1
            if r.failed:
                diffs[d]["failed"] += 1
        for d in diffs:
            t = diffs[d]["total"]
            diffs[d]["success_rate"] = round(diffs[d]["solved"] / t, 3) if t else 0.0
        return diffs

    def agent_metrics(self) -> dict[str, dict]:
        agents: dict[str, dict] = {}
        for r in self._results:
            for agent_name in r.agents_used:
                if agent_name not in agents:
                    agents[agent_name] = {"attempts": 0, "solved": 0, "failed": 0, "success_rate": 0.0}
                agents[agent_name]["attempts"] += 1
                if r.solved:
                    agents[agent_name]["solved"] += 1
                if r.failed:
                    agents[agent_name]["failed"] += 1
        for name in agents:
            t = agents[name]["attempts"]
            agents[name]["success_rate"] = round(agents[name]["solved"] / t, 3) if t else 0.0
        return agents

    def tool_usage(self) -> dict[str, int]:
        usage: dict[str, int] = {}
        for r in self._results:
            for tool in r.tools_used:
                usage[tool] = usage.get(tool, 0) + 1
        return usage

    def failure_breakdown(self) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for r in self._results:
            cat = r.failure_category or "unknown"
            breakdown[cat] = breakdown.get(cat, 0) + 1
        return breakdown

    def all_results(self) -> list[BenchmarkResult]:
        return list(self._results)

    def clear(self) -> None:
        self._results.clear()
