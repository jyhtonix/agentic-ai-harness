"""A/B experiment engine: memory-disabled vs memory-enabled CTF solving.

Runs the same challenge set twice:
  * Cold pass  — the planner/supervisor have NO memory (nothing to retrieve,
                 nothing recorded). Baseline behaviour.
  * Warm pass  — every cold-pass supervisor output is recorded as an episode
                 into a MemoryService, which is then wired into the planner,
                 supervisor and runner. Reuses prior solutions/failures.

Compares: success rate, solving time, agent steps, tool usage and the
strategies actually recovered from memory.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from benchmark_engine.runner import BenchmarkRunner
from benchmark_engine.results import BenchmarkResult
from benchmark_engine.history import BenchmarkHistory
from challenges_engine.loader import ChallengeLoader
from memory.service import MemoryService

logger = logging.getLogger("benchmark_engine.memory_experiment")

DEFAULT_REQUEST = "Solve this CTF challenge and recover the flag."


@dataclass
class ChallengeRun:
    challenge_id: str
    category: str
    solved: bool = False
    execution_time: float = 0.0
    plan_steps: int = 0
    agent_results: int = 0
    tools_used: list = field(default_factory=list)
    agents_used: list = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "challenge_id": self.challenge_id,
            "category": self.category,
            "solved": self.solved,
            "execution_time": self.execution_time,
            "plan_steps": self.plan_steps,
            "agent_results": self.agent_results,
            "tools_used": self.tools_used,
            "agents_used": self.agents_used,
            "confidence": self.confidence,
        }


@dataclass
class ChallengeComparison:
    challenge_id: str
    category: str
    cold: Optional[ChallengeRun] = None
    warm: Optional[ChallengeRun] = None
    recovered_context: str = ""

    def to_dict(self) -> dict:
        return {
            "challenge_id": self.challenge_id,
            "category": self.category,
            "cold": self.cold.to_dict() if self.cold else None,
            "warm": self.warm.to_dict() if self.warm else None,
            "recovered_context": self.recovered_context,
        }


@dataclass
class ModeSummary:
    mode: str
    challenges_attempted: int = 0
    solved: int = 0
    failed: int = 0
    success_rate: float = 0.0
    total_time: float = 0.0
    average_time: float = 0.0
    average_steps: float = 0.0
    tools_used: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "challenges_attempted": self.challenges_attempted,
            "solved": self.solved,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 3),
            "total_time": round(self.total_time, 2),
            "average_time": round(self.average_time, 2),
            "average_steps": round(self.average_steps, 2),
            "tools_used": dict(sorted(self.tools_used.items(), key=lambda x: x[1], reverse=True)),
        }


@dataclass
class MemoryExperimentReport:
    dataset_name: str = ""
    challenge_ids: list = field(default_factory=list)
    comparisons: list = field(default_factory=list)
    cold_summary: Optional[ModeSummary] = None
    warm_summary: Optional[ModeSummary] = None
    memory_summary: dict = field(default_factory=dict)
    improvement: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "dataset_name": self.dataset_name,
            "challenge_ids": self.challenge_ids,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "cold_summary": self.cold_summary.to_dict() if self.cold_summary else None,
            "warm_summary": self.warm_summary.to_dict() if self.warm_summary else None,
            "memory_summary": self.memory_summary,
            "improvement": self.improvement,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), indent=indent)

    def summary_table(self) -> str:
        lines = [
            "=" * 78,
            f"Memory A/B Experiment: {self.dataset_name}",
            "=" * 78,
            f"{'':28s} {'Cold (no memory)':>20s} {'Warm (memory)':>20s}",
            "-" * 78,
        ]
        c, w = self.cold_summary, self.warm_summary
        if c and w:
            lines.append(f"{'Solved':28s} {f'{c.solved}/{c.challenges_attempted}':>20s} {f'{w.solved}/{w.challenges_attempted}':>20s}")
            lines.append(f"{'Success rate':28s} {f'{c.success_rate:.1%}':>20s} {f'{w.success_rate:.1%}':>20s}")
            lines.append(f"{'Total time':28s} {f'{c.total_time:.1f}s':>20s} {f'{w.total_time:.1f}s':>20s}")
            lines.append(f"{'Average time':28s} {f'{c.average_time:.1f}s':>20s} {f'{w.average_time:.1f}s':>20s}")
            lines.append(f"{'Average agent steps':28s} {f'{c.average_steps:.1f}':>20s} {f'{w.average_steps:.1f}':>20s}")
        lines.append("-" * 78)
        lines.append("Per-challenge:")
        lines.append(f"{'Challenge':28s} {'Cold':>20s} {'Warm':>20s}")
        for cmp_ in self.comparisons:
            c_s = "solved" if cmp_.cold and cmp_.cold.solved else ("failed" if cmp_.cold else "n/a")
            w_s = "solved" if cmp_.warm and cmp_.warm.solved else ("failed" if cmp_.warm else "n/a")
            c_t = f"{cmp_.cold.execution_time:.1f}s" if cmp_.cold else "n/a"
            w_t = f"{cmp_.warm.execution_time:.1f}s" if cmp_.warm else "n/a"
            lines.append(f"{cmp_.challenge_id:28s} {f'{c_s} {c_t}':>20s} {f'{w_s} {w_t}':>20s}")
        if self.memory_summary:
            lines.append("-" * 78)
            lines.append(f"Memory populated: {self.memory_summary}")
        if self.improvement:
            lines.append("-" * 78)
            lines.append(f"Improvement: {self.improvement}")
        lines.append("=" * 78)
        return "\n".join(lines)


SupervisorBuilder = Callable[[Optional[MemoryService]], "object"]


class _BoundSupervisor:
    """Binds a SupervisorAgent to a challenge id and captures its output."""

    def __init__(self, supervisor, challenge_id: str):
        self.supervisor = supervisor
        self.challenge_id = challenge_id
        self.output: Optional[dict] = None

    async def run(self) -> dict:
        self.output = await self.supervisor.run(
            DEFAULT_REQUEST,
            challenge_id=self.challenge_id,
        )
        return self.output


class MemoryExperiment:
    def __init__(
        self,
        challenge_ids: list[str],
        supervisor_builder: SupervisorBuilder,
        loader: Optional[ChallengeLoader] = None,
        memory_dir: Optional[str] = None,
        max_attempts: Optional[int] = None,
        dataset_name: str = "memory_ab",
        history: Optional[BenchmarkHistory] = None,
    ):
        self.challenge_ids = list(challenge_ids)
        self.supervisor_builder = supervisor_builder
        self.loader = loader or ChallengeLoader()
        self.memory_dir = memory_dir
        self.max_attempts = max_attempts
        self.dataset_name = dataset_name
        self.history = history
        self.memory: Optional[MemoryService] = None
        self.cold_runs: list[ChallengeRun] = []
        self.warm_runs: list[ChallengeRun] = []
        self.cold_outputs: list[Optional[dict]] = []
        self.warm_outputs: list[Optional[dict]] = []

    # ------------------------------------------------------------------
    # Public flow
    # ------------------------------------------------------------------

    async def run(self) -> MemoryExperimentReport:
        self.cold_runs, self.cold_outputs = await self._run_pass(memory_service=None)
        self.memory = self._seed_memory()
        self.warm_runs, self.warm_outputs = await self._run_pass(memory_service=self.memory)
        return self._build_report()

    # ------------------------------------------------------------------
    # Passes
    # ------------------------------------------------------------------

    async def _run_pass(
        self, memory_service: Optional[MemoryService]
    ) -> tuple[list[ChallengeRun], list[Optional[dict]]]:
        runs: list[ChallengeRun] = []
        outputs: list[Optional[dict]] = []
        for cid in self.challenge_ids:
            challenge = self.loader.load(cid)
            if challenge is None:
                logger.warning("Skipping unknown challenge: %s", cid)
                continue

            supervisor = await self.supervisor_builder(memory_service)
            bound = _BoundSupervisor(supervisor, cid)
            runner = BenchmarkRunner(
                challenge_loader=self.loader,
                supervisor_factory=bound.run,
                learning_service=memory_service if memory_service else None,
                history=self.history,
            )
            result = await runner.run_challenge(cid, max_attempts=self.max_attempts)
            runs.append(self._to_challenge_run(result, bound.output))
            outputs.append(bound.output)

        logger.info(
            "Pass complete (memory=%s): %d/%d solved",
            "enabled" if memory_service else "disabled",
            sum(1 for r in runs if r.solved),
            len(runs),
        )
        return runs, outputs

    def _seed_memory(self) -> MemoryService:
        service = MemoryService(memory_dir=self.memory_dir)
        for output in self.cold_outputs:
            if output:
                service.record_supervisor_output(output)
        summary = service.get_summary()
        logger.info("Seeded memory: %s", summary)
        return service

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_challenge_run(result: BenchmarkResult, output: Optional[dict]) -> ChallengeRun:
        output = output or {}
        plan = output.get("plan") or []
        agent_results = output.get("agent_results") or []
        return ChallengeRun(
            challenge_id=result.challenge_id,
            category=result.category,
            solved=result.solved,
            execution_time=result.execution_time,
            plan_steps=len(plan) if isinstance(plan, list) else 0,
            agent_results=len(agent_results) if isinstance(agent_results, list) else 0,
            tools_used=list(result.tools_used or []),
            agents_used=list(result.agents_used or []),
            confidence=result.confidence,
        )

    def _build_report(self) -> MemoryExperimentReport:
        report = MemoryExperimentReport(
            dataset_name=self.dataset_name,
            challenge_ids=self.challenge_ids,
        )

        cold_by_id = {r.challenge_id: r for r in self.cold_runs}
        warm_by_id = {r.challenge_id: r for r in self.warm_runs}

        for cid in self.challenge_ids:
            if cid not in cold_by_id and cid not in warm_by_id:
                continue
            cmp_ = ChallengeComparison(
                challenge_id=cid,
                category=cold_by_id.get(cid, warm_by_id.get(cid)).category,
                cold=cold_by_id.get(cid),
                warm=warm_by_id.get(cid),
                recovered_context=self._recovered_context(cid),
            )
            report.comparisons.append(cmp_)

        report.cold_summary = self._summarize("cold", self.cold_runs)
        report.warm_summary = self._summarize("warm", self.warm_runs)
        report.memory_summary = self.memory.get_summary() if self.memory else {}
        report.improvement = self._compute_improvement(report)
        return report

    def _recovered_context(self, challenge_id: str) -> str:
        if not self.memory:
            return ""
        challenge = self.loader.load(challenge_id)
        if not challenge:
            return ""
        try:
            return self.memory.format_context(
                challenge.category, query=challenge.description, limit=3
            )
        except Exception:
            logger.exception("Failed to format recovered context for %s", challenge_id)
            return ""

    @staticmethod
    def _summarize(mode: str, runs: list[ChallengeRun]) -> ModeSummary:
        summary = ModeSummary(mode=mode)
        if not runs:
            return summary
        summary.challenges_attempted = len(runs)
        summary.solved = sum(1 for r in runs if r.solved)
        summary.failed = len(runs) - summary.solved
        summary.success_rate = summary.solved / len(runs)
        summary.total_time = sum(r.execution_time for r in runs)
        times = [r.execution_time for r in runs if r.execution_time > 0]
        summary.average_time = sum(times) / len(times) if times else 0.0
        steps = [r.plan_steps + r.agent_results for r in runs]
        summary.average_steps = sum(steps) / len(steps) if steps else 0.0
        for r in runs:
            for tool in r.tools_used:
                summary.tools_used[tool] = summary.tools_used.get(tool, 0) + 1
        return summary

    @staticmethod
    def _compute_improvement(report: MemoryExperimentReport) -> str:
        c, w = report.cold_summary, report.warm_summary
        if not c or not w:
            return ""
        if w.challenges_attempted == 0:
            return ""
        delta_rate = w.success_rate - c.success_rate
        delta_time = c.average_time - w.average_time
        return (
            f"Success rate {c.success_rate:.1%} -> {w.success_rate:.1%} "
            f"({delta_rate:+.1%}); avg time {c.average_time:.1f}s -> {w.average_time:.1f}s "
            f"({delta_time:+.1f}s)"
        )
