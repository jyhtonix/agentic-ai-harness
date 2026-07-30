"""Performance comparison engine for benchmarking different model configurations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from benchmark_engine.metrics import MetricsCollector
from benchmark_engine.model_runner import ModelBenchmarkResult


@dataclass
class ModelComparisonEntry:
    model_name: str
    model_id: str
    challenges_attempted: int = 0
    solved: int = 0
    failed: int = 0
    success_rate: float = 0.0
    average_confidence: float = 0.0
    average_time: float = 0.0
    total_time: float = 0.0
    tools_used: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "model_id": self.model_id,
            "challenges_attempted": self.challenges_attempted,
            "solved": self.solved,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 3),
            "average_confidence": round(self.average_confidence, 3),
            "average_time": round(self.average_time, 2),
            "total_time": round(self.total_time, 2),
            "tools_used": dict(sorted(self.tools_used.items(), key=lambda x: x[1], reverse=True)),
        }


@dataclass
class ComparisonReport:
    dataset_name: str = ""
    models: list[ModelComparisonEntry] = field(default_factory=list)
    best_model: str = ""
    best_rate: float = 0.0
    overall_improvement: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "dataset_name": self.dataset_name,
            "models": [m.to_dict() for m in self.models],
            "best_model": self.best_model,
            "best_rate": self.best_rate,
            "overall_improvement": self.overall_improvement,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def summary_table(self) -> str:
        lines = [
            "=" * 70,
            f"Model Comparison Report: {self.dataset_name}",
            "=" * 70,
            f"{'Model':30s} {'Attempted':>10s} {'Solved':>8s} {'Rate':>8s} {'Conf':>8s} {'Time':>8s}",
            "-" * 70,
        ]
        for m in self.models:
            lines.append(
                f"{m.model_name:30s} {m.challenges_attempted:>10d} {m.solved:>8d} "
                f"{m.success_rate:>7.1%} {m.average_confidence:>7.2f} {m.average_time:>7.1f}s"
            )
        lines.append("-" * 70)
        if self.best_model:
            lines.append(f"Best Model: {self.best_model} ({self.best_rate:.1%})")
        if self.overall_improvement:
            lines.append(f"Improvement: {self.overall_improvement}")
        lines.append("=" * 70)
        return "\n".join(lines)


class ComparisonEngine:
    def __init__(self):
        self._model_metrics: dict[str, MetricsCollector] = {}

    def add_model_results(self, model_id: str, results: list[ModelBenchmarkResult]) -> None:
        mc = MetricsCollector()
        mc.record_many(results)
        self._model_metrics[model_id] = mc

    def add_model_metrics(self, model_id: str, metrics: MetricsCollector) -> None:
        self._model_metrics[model_id] = metrics

    def compare(self, dataset_name: str = "unnamed") -> ComparisonReport:
        report = ComparisonReport(dataset_name=dataset_name)

        for model_id, mc in self._model_metrics.items():
            tool_usage = mc.tool_usage()
            entry = ModelComparisonEntry(
                model_name=model_id,
                model_id=model_id,
                challenges_attempted=mc.total,
                solved=mc.solved,
                failed=mc.failed,
                success_rate=mc.success_rate,
                average_confidence=mc.average_confidence,
                total_time=mc.total_execution_time,
                tools_used=tool_usage,
            )

            times = [r.execution_time for r in mc.all_results() if r.execution_time > 0]
            entry.average_time = round(sum(times) / len(times), 2) if times else 0.0
            report.models.append(entry)

        report.models.sort(key=lambda m: m.success_rate, reverse=True)
        if report.models:
            best = report.models[0]
            report.best_model = best.model_name
            report.best_rate = best.success_rate

            if len(report.models) >= 2:
                worst = report.models[-1]
                gap = best.success_rate - worst.success_rate
                report.overall_improvement = (
                    f"Best ({best.model_name}) outperforms worst ({worst.model_name}) "
                    f"by {gap:.1%}"
                )

        return report

    def clear(self) -> None:
        self._model_metrics.clear()
