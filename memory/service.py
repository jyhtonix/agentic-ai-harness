"""MemoryService — facade over the memory stores for the CTF learning loop.

Provides:
  * record()          — persist a rich episode (success or failure)
  * retrieve_context()— query prior similar experiences for a challenge
  * format_context()  — render retrieved knowledge for planner injection
"""

from __future__ import annotations

import logging
from typing import Optional

from memory.strategies import StrategyMemory
from memory.failures import FailureMemory
from memory.solutions import SolutionMemory
from memory.episode import CTFEpisode, build_episode_from_supervisor_output
from learning_engine.learner import AutonomousLearner
from learning_engine.updater import KnowledgeUpdater
from benchmark_engine.results import BenchmarkResult

logger = logging.getLogger("memory.service")


class MemoryService:
    def __init__(
        self,
        strategy_memory: Optional[StrategyMemory] = None,
        failure_memory: Optional[FailureMemory] = None,
        solution_memory: Optional[SolutionMemory] = None,
        learner: Optional[AutonomousLearner] = None,
        updater: Optional[KnowledgeUpdater] = None,
        memory_dir: Optional[str] = None,
    ):
        kwargs = {"storage_dir": memory_dir} if memory_dir else {}
        self.strategy_memory = strategy_memory or StrategyMemory(**kwargs)
        self.failure_memory = failure_memory or FailureMemory(**kwargs)
        self.solution_memory = solution_memory or SolutionMemory(**kwargs)
        self.learner = learner or AutonomousLearner(
            strategy_memory=self.strategy_memory,
            failure_memory=self.failure_memory,
            solution_memory=self.solution_memory,
        )
        self.updater = updater or KnowledgeUpdater(
            strategy_memory=self.strategy_memory,
            failure_memory=self.failure_memory,
            solution_memory=self.solution_memory,
        )

    # ------------------------------------------------------------------
    # Recording (after a challenge)
    # ------------------------------------------------------------------

    def record_episode(self, episode: CTFEpisode) -> dict:
        """Persist a rich episode and run the learning loop on it."""
        result = self._episode_to_result(episode)
        entry = self.learner.learn_from_result(result, episode=episode.to_dict())
        if entry.get("actions_taken"):
            self.updater.update_from_learning(entry)
        return entry

    def record_result(self, result: BenchmarkResult, episode: Optional[dict] = None) -> dict:
        """Persist a benchmark result (with optional rich episode) via the learner."""
        entry = self.learner.learn_from_result(result, episode=episode)
        if entry.get("actions_taken"):
            self.updater.update_from_learning(entry)
        return entry

    def record_supervisor_output(self, output: dict) -> Optional[dict]:
        """Build an episode from a SupervisorAgent.run() result and persist it."""
        episode = build_episode_from_supervisor_output(output)
        if episode is None:
            return None
        return self.record_episode(episode)

    # ------------------------------------------------------------------
    # Retrieval (before a challenge)
    # ------------------------------------------------------------------

    @staticmethod
    def _episode_to_result(episode: CTFEpisode) -> BenchmarkResult:
        """Convert a CTFEpisode into a BenchmarkResult for the learning loop."""
        return BenchmarkResult(
            challenge_id=episode.challenge_id,
            category=episode.category,
            difficulty=episode.difficulty,
            status=episode.status,
            flag_result=episode.flag_result,
            execution_time=episode.execution_time,
            confidence=episode.confidence,
            attempts=episode.attempts,
            tools_used=episode.tools_used,
            agents_used=episode.agents_used,
            failure_reason=episode.failure_reason,
        )

    def retrieve_context(self, category: str, query: str = "",
                         limit: int = 3) -> dict:
        """Query prior similar experiences for a category."""
        return {
            "category": category,
            "solutions": self.solution_memory.get_relevant(
                category, query=query, limit=limit, success=True
            ),
            "failures": self.failure_memory.get_relevant(
                category, query=query, limit=limit
            ),
            "strategies": self.strategy_memory.get_strategies(category),
            "avoid": self.strategy_memory.get_failed_approaches(category),
        }

    def format_context(self, category: str, query: str = "",
                       limit: int = 3) -> str:
        """Render prior knowledge as prompt text for planner injection."""
        context = self.retrieve_context(category, query=query, limit=limit)
        sections = []

        solutions = context["solutions"]
        if solutions:
            lines = []
            for s in solutions:
                approach = s.get("approach", "")
                tools = ", ".join(s.get("tools_used", []))
                desc = s.get("description", "")[:160]
                techniques = "; ".join(s.get("successful_techniques", []))[:200]
                reasoning = s.get("final_solution_reasoning", "")[:300]
                header = f"- Approach: {approach}"
                if tools:
                    header += f" | tools: {tools}"
                lines.append(header)
                if desc:
                    lines.append(f"    challenge: {desc}")
                if techniques:
                    lines.append(f"    techniques: {techniques}")
                if reasoning:
                    lines.append(f"    reasoning: {reasoning}")
            sections.append("## Prior successful solutions (reuse these techniques)\n" + "\n".join(lines))

        failures = context["failures"]
        if failures:
            lines = []
            for f in failures:
                reason = f.get("reason", "")
                rec = f.get("recommendation", "")
                line = f"- Avoid: {reason}"
                if rec:
                    line += f" (suggestion: {rec})"
                lines.append(line)
            sections.append("## Prior failures (avoid repeating these)\n" + "\n".join(lines))

        if context["strategies"]:
            sections.append("## Proven strategies\n" + "\n".join(
                f"- {s}" for s in context["strategies"][:limit]
            ))

        if context["avoid"]:
            sections.append("## Approaches to avoid\n" + "\n".join(
                f"- {a}" for a in context["avoid"][:limit]
            ))

        if not sections:
            return ""

        return ("\n\nRelevant prior CTF experience retrieved from memory:\n"
                + "\n\n".join(sections))

    def get_summary(self) -> dict:
        return {
            "solutions_stored": len(self.solution_memory.get_solutions()),
            "failures_stored": len(self.failure_memory.get_failures()),
            "strategies": len(self.strategy_memory.get_all()),
        }
