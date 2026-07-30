"""AutonomousLearner — orchestrates the self-improvement loop."""

from __future__ import annotations

import logging
from typing import Optional

from benchmark_engine.results import BenchmarkResult
from benchmark_engine.failure import FailureAnalyzer
from benchmark_engine.skill_gap import SkillGapDetector
from benchmark_engine.strategy_evolution import StrategyEvolutionEngine
from memory.strategies import StrategyMemory
from memory.failures import FailureMemory
from memory.solutions import SolutionMemory

logger = logging.getLogger("learning_engine.learner")


class AutonomousLearner:
    def __init__(
        self,
        failure_analyzer: Optional[FailureAnalyzer] = None,
        skill_gap_detector: Optional[SkillGapDetector] = None,
        strategy_evolution: Optional[StrategyEvolutionEngine] = None,
        strategy_memory: Optional[StrategyMemory] = None,
        failure_memory: Optional[FailureMemory] = None,
        solution_memory: Optional[SolutionMemory] = None,
    ):
        self.failure_analyzer = failure_analyzer or FailureAnalyzer()
        self.skill_gap_detector = skill_gap_detector or SkillGapDetector()
        self.strategy_evolution = strategy_evolution or StrategyEvolutionEngine()
        self.strategy_memory = strategy_memory or StrategyMemory()
        self.failure_memory = failure_memory or FailureMemory()
        self.solution_memory = solution_memory or SolutionMemory()
        self._learning_log: list[dict] = []

    def learn_from_result(self, result: BenchmarkResult) -> dict:
        entry = {
            "challenge_id": result.challenge_id,
            "status": result.status,
            "category": result.category,
        }

        if result.solved:
            return self._process_success(result, entry)

        return self._process_failure(result, entry)

    def learn_from_results(self, results: list[BenchmarkResult]) -> list[dict]:
        return [self.learn_from_result(r) for r in results]

    def get_improvement_summary(self) -> dict:
        skill_gaps = self.skill_gap_detector.get_top_gaps()
        improvement_count = len([e for e in self._learning_log if e.get("actions_taken")])

        return {
            "total_challenges_processed": len(self._learning_log),
            "improvement_opportunities": improvement_count,
            "top_skill_gaps": skill_gaps,
            "memory_update_count": len(self._learning_log),
        }

    def _process_success(self, result: BenchmarkResult, entry: dict) -> dict:
        self.solution_memory.record(
            challenge_id=result.challenge_id,
            category=result.category,
            difficulty=result.difficulty,
            approach="solved_with_strategy_" + "_".join(result.agents_used),
            tools_used=result.tools_used,
            agents_used=result.agents_used,
            success=True,
        )
        self.strategy_memory.record(
            result.category,
            f"Solved with: {'/'.join(result.agents_used)}",
            confidence=result.confidence,
        )
        entry["actions_taken"] = ["recorded_solution", "updated_strategy_memory"]
        entry["improvement"] = "success_recorded"
        self._learning_log.append(entry)
        return entry

    def _process_failure(self, result: BenchmarkResult, entry: dict) -> dict:
        analysis = self.failure_analyzer.analyze(result)
        skill_gap = self.skill_gap_detector.analyze(result)
        evolved = self.strategy_evolution.evolve(result.category, [result])

        self.failure_memory.record(
            challenge_id=result.challenge_id,
            category=result.category,
            reason=result.failure_reason or analysis.get("reason", ""),
            failure_type=analysis.get("category", "unknown"),
            recommendation=analysis.get("recommendation", ""),
        )

        actions = ["recorded_failure"]
        if skill_gap.get("gaps"):
            actions.append("detected_skill_gaps")
        if evolved:
            actions.append("evolved_strategy")

        entry["actions_taken"] = actions
        entry["failure_analysis"] = analysis
        entry["skill_gaps"] = skill_gap
        entry["evolved_strategy"] = evolved
        entry["improvement"] = "failure_analyzed"
        self._learning_log.append(entry)
        return entry
