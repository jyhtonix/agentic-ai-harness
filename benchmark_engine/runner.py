from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Callable, Awaitable

from benchmark_engine.results import BenchmarkResult
from benchmark_engine.metrics import MetricsCollector
from benchmark_engine.retry import RetryController
from benchmark_engine.failure import FailureAnalyzer
from benchmark_engine.history import BenchmarkHistory

from challenges_engine.loader import ChallengeLoader

logger = logging.getLogger("benchmark_engine.runner")

SupervisorFactory = Callable[[], Awaitable]


class BenchmarkRunner:
    def __init__(
        self,
        challenge_loader: Optional[ChallengeLoader] = None,
        supervisor_factory: Optional[SupervisorFactory] = None,
        retry_controller: Optional[RetryController] = None,
        failure_analyzer: Optional[FailureAnalyzer] = None,
        history: Optional[BenchmarkHistory] = None,
        learning_service=None,
    ):
        self.challenge_loader = challenge_loader or ChallengeLoader()
        self.supervisor_factory = supervisor_factory
        self.retry_controller = retry_controller or RetryController()
        self.failure_analyzer = failure_analyzer or FailureAnalyzer()
        self.history = history or BenchmarkHistory()
        self.learning_service = learning_service
        self.metrics = MetricsCollector()

    async def run_challenge(self, challenge_id: str, max_attempts: Optional[int] = None) -> BenchmarkResult:
        challenge = self.challenge_loader.load(challenge_id)
        if challenge is None:
            logger.warning("Challenge not found: %s", challenge_id)
            return BenchmarkResult(
                challenge_id=challenge_id,
                category="unknown",
                difficulty="unknown",
                status="error",
                failure_reason=f"Challenge '{challenge_id}' not found",
                failure_category="not_found",
            )

        super_call = self.supervisor_factory
        if super_call is None:

            async def _noop():
                return self._make_empty_result(challenge_id)

            super_call = _noop

        effective_max = max_attempts if max_attempts is not None else self.retry_controller.max_attempts

        last_result: Optional[BenchmarkResult] = None
        supervisor_result: Optional[dict] = None
        for attempt in range(1, effective_max + 1):
            logger.info("Benchmark attempt %d/%d for %s", attempt, effective_max, challenge_id)

            start = time.time()
            try:
                supervisor_result = await super_call()
            except Exception as e:
                elapsed = round(time.time() - start, 3)
                last_result = BenchmarkResult(
                    challenge_id=challenge_id,
                    category=challenge.category,
                    difficulty=challenge.difficulty,
                    status="error",
                    execution_time=elapsed,
                    attempts=attempt,
                    failure_reason=str(e),
                    failure_category="runtime_error",
                )
                self.metrics.record(last_result)
                break

            elapsed = round(time.time() - start, 3)
            result = self._extract_result(supervisor_result, challenge_id, challenge.category, challenge.difficulty, elapsed, attempt)
            last_result = result

            if result.solved:
                logger.info("Challenge %s solved on attempt %d", challenge_id, attempt)
                break

            if attempt < effective_max:
                strategy = self.failure_analyzer.analyze(result)
                self.retry_controller.register_failure(challenge_id, strategy)
                logger.info("Attempt %d failed. Strategy: %s", attempt, strategy.get("recommendation", "retry"))

        if last_result:
            self.metrics.record(last_result)
            self.history.save(last_result)
            await self._record_learning(last_result, supervisor_result)
        return last_result or BenchmarkResult(
            challenge_id=challenge_id, category="unknown", difficulty="unknown", status="error"
        )

    async def _record_learning(self, result: BenchmarkResult, supervisor_result: Optional[dict]) -> None:
        """Feed the challenge result into the memory/learning loop."""
        if not self.learning_service:
            return
        try:
            if supervisor_result and isinstance(supervisor_result, dict):
                self.learning_service.record_supervisor_output(supervisor_result)
            else:
                self.learning_service.record_result(result)
        except Exception as e:
            logger.warning("Learning capture failed for %s: %s", result.challenge_id, e)

    async def run_dataset(self, challenge_ids: list[str], max_attempts: Optional[int] = None) -> list[BenchmarkResult]:
        results: list[BenchmarkResult] = []
        for cid in challenge_ids:
            result = await self.run_challenge(cid, max_attempts)
            results.append(result)
        return results

    def _extract_result(
        self, supervisor_result: dict, challenge_id: str,
        category: str, difficulty: str, elapsed: float, attempt: int
    ) -> BenchmarkResult:
        flag_verification = supervisor_result.get("flag_verification") or {}
        verification = supervisor_result.get("verification") or {}
        agent_results = supervisor_result.get("agent_results") or []
        learning_report = supervisor_result.get("learning_report") or {}

        flag_status = flag_verification.get("status", "")
        solved = flag_status == "PASS"

        agents_used = list({r.get("agent", "") for r in agent_results if r.get("agent")})
        tools_used = learning_report.get("tools_used", []) or []
        confidence = verification.get("confidence_score", 0) or 0

        return BenchmarkResult(
            challenge_id=challenge_id,
            category=category,
            difficulty=difficulty,
            status="solved" if solved else "failed",
            flag_result=flag_status,
            execution_time=elapsed,
            confidence=confidence,
            attempts=attempt,
            tools_used=tools_used,
            agents_used=agents_used,
            verification_details=verification if isinstance(verification, dict) else None,
        )

    @staticmethod
    def _make_empty_result(challenge_id: str) -> dict:
        return {
            "request": "",
            "analysis": "",
            "plan": [],
            "agent_results": [],
            "verification": None,
            "learning_report": None,
            "flag_verification": None,
            "challenge": None,
            "team_coordination": None,
            "final_response": "",
        }
