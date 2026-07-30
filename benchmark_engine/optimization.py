"""Optimization report generator for the CTF validation framework."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from benchmark_engine.metrics import MetricsCollector
from benchmark_engine.failure import FailureAnalyzer
from benchmark_engine.comparison import ComparisonReport


@dataclass
class CapabilitySummary:
    category: str
    success_rate: float
    solved: int
    total: int
    average_confidence: float
    common_failures: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "success_rate": round(self.success_rate, 3),
            "solved": self.solved,
            "total": self.total,
            "average_confidence": round(self.average_confidence, 3),
            "common_failures": self.common_failures,
            "recommendations": self.recommendations,
        }


@dataclass
class OptimizationReport:
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dataset_name: str = ""
    total_challenges: int = 0
    overall_success_rate: float = 0.0
    capabilities: list[CapabilitySummary] = field(default_factory=list)
    weakest_category: str = ""
    strongest_category: str = ""
    tool_recommendations: list[str] = field(default_factory=list)
    skill_recommendations: list[str] = field(default_factory=list)
    agent_recommendations: list[str] = field(default_factory=list)
    model_comparison: Optional[ComparisonReport] = None
    improvement_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "generated_at": self.generated_at,
            "dataset_name": self.dataset_name,
            "total_challenges": self.total_challenges,
            "overall_success_rate": round(self.overall_success_rate, 3),
            "capabilities": [c.to_dict() for c in self.capabilities],
            "weakest_category": self.weakest_category,
            "strongest_category": self.strongest_category,
            "tool_recommendations": self.tool_recommendations,
            "skill_recommendations": self.skill_recommendations,
            "agent_recommendations": self.agent_recommendations,
            "improvement_actions": self.improvement_actions,
        }
        if self.model_comparison:
            d["model_comparison"] = self.model_comparison.to_dict()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def summary_table(self) -> str:
        lines = [
            "=" * 70,
            f"Optimization Report: {self.dataset_name}",
            "=" * 70,
            f"  Overall Success Rate: {self.overall_success_rate:.1%}",
            f"  Total Challenges:     {self.total_challenges}",
            "",
            "Capability by Category:",
        ]
        for cap in self.capabilities:
            bar = "#" * int(cap.success_rate * 20) + "." * (20 - int(cap.success_rate * 20))
            lines.append(
                f"  {cap.category:15s} [{bar}] {cap.success_rate:.0%}  "
                f"({cap.solved}/{cap.total})"
            )
        if self.weakest_category:
            lines.append("")
            lines.append(f"Weakest Area:  {self.weakest_category}")
        if self.strongest_category:
            lines.append(f"Strongest Area: {self.strongest_category}")
        if self.improvement_actions:
            lines.append("")
            lines.append("Improvement Actions:")
            for a in self.improvement_actions:
                lines.append(f"  - {a}")
        lines.append("=" * 70)
        return "\n".join(lines)


class OptimizationEngine:
    def __init__(self, metrics: Optional[MetricsCollector] = None,
                 failure_analyzer: Optional[FailureAnalyzer] = None):
        self.metrics = metrics or MetricsCollector()
        self.failure_analyzer = failure_analyzer or FailureAnalyzer()

    def generate(self, dataset_name: str = "unnamed",
                 model_comparison: Optional[ComparisonReport] = None) -> OptimizationReport:
        report = OptimizationReport(
            dataset_name=dataset_name,
            total_challenges=self.metrics.total,
            overall_success_rate=self.metrics.success_rate,
            model_comparison=model_comparison,
        )

        by_cat = self.metrics.by_category()
        all_results = self.metrics.all_results()

        for cat, stats in sorted(by_cat.items()):
            cat_results = [r for r in all_results if r.category == cat]
            confs = [r.confidence for r in cat_results if r.confidence > 0]
            avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0

            failures = []
            recs = []
            for r in cat_results:
                if r.failed:
                    analysis = self.failure_analyzer.analyze(r)
                    failures.append(analysis.get("category", "unknown"))
                    r_rec = analysis.get("recommendation", "")
                    if r_rec and r_rec not in recs:
                        recs.append(r_rec)

            report.capabilities.append(CapabilitySummary(
                category=cat,
                success_rate=stats.get("success_rate", 0),
                solved=stats.get("solved", 0),
                total=stats.get("total", 0),
                average_confidence=avg_conf,
                common_failures=sorted(set(failures)),
                recommendations=recs[:3],
            ))

        if report.capabilities:
            sorted_caps = sorted(report.capabilities, key=lambda c: c.success_rate)
            report.weakest_category = f"{sorted_caps[0].category} ({sorted_caps[0].success_rate:.0%})"
            report.strongest_category = f"{sorted_caps[-1].category} ({sorted_caps[-1].success_rate:.0%})"

        report.improvement_actions = self._generate_actions(report.capabilities)
        return report

    @staticmethod
    def _generate_actions(capabilities: list[CapabilitySummary]) -> list[str]:
        actions = []
        for cap in capabilities:
            if cap.success_rate < 0.5 and cap.total >= 2:
                actions.append(
                    f"Improve {cap.category} capability ({cap.success_rate:.0%} success). "
                    f"Common failures: {', '.join(cap.common_failures[:3])}."
                )
                for rec in cap.recommendations[:2]:
                    actions.append(f"  -> {rec}")
            elif cap.success_rate < 0.8 and cap.total >= 2:
                actions.append(
                    f"Strengthen {cap.category} capability ({cap.success_rate:.0%} success). "
                    f"Review {', '.join(cap.common_failures[:2])} patterns."
                )
        return actions
