from __future__ import annotations

from typing import Optional

from benchmark_engine.metrics import MetricsCollector
from benchmark_engine.results import BenchmarkReport


class Evaluator:
    def __init__(self, metrics: Optional[MetricsCollector] = None):
        self.metrics = metrics or MetricsCollector()

    def generate_report(self, dataset_name: str = "unnamed") -> BenchmarkReport:
        report = BenchmarkReport(dataset_name=dataset_name)

        all_results = self.metrics.all_results()
        report.total_challenges = self.metrics.total
        report.solved = self.metrics.solved
        report.failed = self.metrics.failed
        report.partial = self.metrics.partial
        report.total_execution_time = self.metrics.total_execution_time
        report.average_confidence = self.metrics.average_confidence
        report.success_rate = self.metrics.success_rate
        report.by_category = self.metrics.by_category()
        report.by_difficulty = self.metrics.by_difficulty()
        report.agent_performance = self.metrics.agent_metrics()
        report.tool_usage = self.metrics.tool_usage()
        report.failure_breakdown = self.metrics.failure_breakdown()
        report.results = [r.to_dict() for r in all_results]

        report.weakest_area = self._find_weakest_category(report.by_category)
        report.recommendations = self._generate_recommendations(report)

        return report

    @staticmethod
    def _find_weakest_category(by_category: dict[str, dict]) -> str:
        if not by_category:
            return ""
        worst = min(by_category.items(), key=lambda x: x[1].get("success_rate", 1.0))
        return f"{worst[0]} ({worst[1].get('success_rate', 0):.1%})"

    @staticmethod
    def _generate_recommendations(report: BenchmarkReport) -> list[str]:
        recs = []

        if report.success_rate < 0.5:
            recs.append("Overall success rate is below 50%. Review agent reasoning pipelines.")
        elif report.success_rate < 0.7:
            recs.append("Success rate is acceptable but has room for improvement.")

        for cat, stats in sorted(report.by_category.items()):
            rate = stats.get("success_rate", 0)
            total = stats.get("total", 0)
            if rate < 0.5 and total >= 2:
                recs.append(f"Improve {cat} category: {rate:.0%} success rate suggests skill or tool gaps.")

        worst_agent = None
        worst_rate = 1.0
        for name, stats in report.agent_performance.items():
            rate = stats.get("success_rate", 0)
            if rate < worst_rate and stats.get("attempts", 0) >= 2:
                worst_rate = rate
                worst_agent = name
        if worst_agent and worst_rate < 0.5:
            recs.append(f"Weak agent: {worst_agent} ({worst_rate:.0%} success rate). Review its reasoning.")

        failure_by_type = report.failure_breakdown
        if failure_by_type:
            top_failure = max(failure_by_type.items(), key=lambda x: x[1])
            recs.append(f"Most common failure type: '{top_failure[0]}' ({top_failure[1]} occurrences).")

        return recs
