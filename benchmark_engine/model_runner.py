"""Model-specific benchmark runner. Compares different AI model configurations."""

from __future__ import annotations

import logging
import time
from typing import Optional, Callable, Awaitable

from benchmark_engine.results import BenchmarkResult
from benchmark_engine.metrics import MetricsCollector
from benchmark_engine.runner import BenchmarkRunner
from models import ModelConfig, ModelRegistry

logger = logging.getLogger("benchmark_engine.model_runner")


class ModelBenchmarkResult(BenchmarkResult):
    def __init__(self, model_name: str = "", model_id: str = "", **kwargs):
        super().__init__(**kwargs)
        self.model_name = model_name
        self.model_id = model_id

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["model_name"] = self.model_name
        d["model_id"] = self.model_id
        return d


ModelFactory = Callable[[ModelConfig], Awaitable]


class ModelBenchmarkRunner:
    def __init__(
        self,
        model_registry: Optional[ModelRegistry] = None,
        model_factory: Optional[ModelFactory] = None,
        benchmark_runner: Optional[BenchmarkRunner] = None,
    ):
        self.model_registry = model_registry or ModelRegistry()
        self.model_factory = model_factory
        self.benchmark_runner = benchmark_runner
        self.results_by_model: dict[str, list[ModelBenchmarkResult]] = {}

    async def run_model(
        self,
        model_id: str,
        challenge_ids: list[str],
        max_attempts: Optional[int] = None,
    ) -> list[ModelBenchmarkResult]:
        config = self.model_registry.get(model_id)
        if config is None:
            logger.warning("Model not found: %s", model_id)
            return []

        logger.info("Running benchmark for model: %s (%s)", config.name, model_id)

        results: list[ModelBenchmarkResult] = []
        for cid in challenge_ids:
            if self.benchmark_runner:
                base = await self.benchmark_runner.run_challenge(cid, max_attempts)
            elif self.model_factory:
                base = await self._run_with_factory(config, cid, max_attempts)
            else:
                logger.warning("No runner or factory available for %s", cid)
                base = BenchmarkResult(
                    challenge_id=cid, category="unknown", difficulty="unknown", status="error",
                    failure_reason="No execution method configured",
                )

            mr = ModelBenchmarkResult(
                model_name=config.name,
                model_id=model_id,
                challenge_id=base.challenge_id,
                category=base.category,
                difficulty=base.difficulty,
                status=base.status,
                flag_result=base.flag_result,
                execution_time=base.execution_time,
                confidence=base.confidence,
                attempts=base.attempts,
                tools_used=base.tools_used,
                agents_used=base.agents_used,
                failure_reason=base.failure_reason,
                failure_category=base.failure_category,
            )
            results.append(mr)

        self.results_by_model[model_id] = results
        logger.info("Model %s: %d/%d solved", config.name,
                     sum(1 for r in results if r.solved), len(results))
        return results

    async def run_models(
        self,
        model_ids: list[str],
        challenge_ids: list[str],
        max_attempts: Optional[int] = None,
    ) -> dict[str, list[ModelBenchmarkResult]]:
        all_results: dict[str, list[ModelBenchmarkResult]] = {}
        for mid in model_ids:
            results = await self.run_model(mid, challenge_ids, max_attempts)
            all_results[mid] = results
        return all_results

    def get_model_metrics(self, model_id: str) -> MetricsCollector:
        mc = MetricsCollector()
        results = self.results_by_model.get(model_id, [])
        mc.record_many(results)
        return mc

    @staticmethod
    async def _run_with_factory(config: ModelConfig, challenge_id: str, max_attempts: Optional[int]) -> BenchmarkResult:
        logger.info("Factory execution for %s with model %s", challenge_id, config.name)
        return BenchmarkResult(
            challenge_id=challenge_id,
            category="unknown",
            difficulty="unknown",
            status="failed",
            failure_reason="Model factory not implemented",
        )
