"""Autonomous Improvement Report generator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from benchmark_engine.metrics import MetricsCollector
from benchmark_engine.skill_gap import SkillGapDetector
from memory.strategy_ranker import StrategyRanker
from skills_engine.improvement import SkillImprovementProposal


@dataclass
class ImprovementDelta:
    metric: str = ""
    previous_value: float = 0.0
    current_value: float = 0.0
    change: float = 0.0

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "previous": round(self.previous_value, 3),
            "current": round(self.current_value, 3),
            "change": round(self.change, 3),
        }


@dataclass
class AutonomousImprovementReport:
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_success_rate: float = 0.0
    current_success_rate: float = 0.0
    improvement_delta: float = 0.0
    deltas: list[ImprovementDelta] = field(default_factory=list)
    improvements_made: list[str] = field(default_factory=list)
    skill_proposals: list[dict] = field(default_factory=list)
    top_strategies: dict[str, list[str]] = field(default_factory=dict)
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "previous_success_rate": round(self.previous_success_rate, 3),
            "current_success_rate": round(self.current_success_rate, 3),
            "improvement_delta": round(self.improvement_delta, 3),
            "deltas": [d.to_dict() for d in self.deltas],
            "improvements_made": self.improvements_made,
            "skill_proposals": self.skill_proposals,
            "top_strategies": self.top_strategies,
            "recommended_actions": self.recommended_actions,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def summary_table(self) -> str:
        lines = [
            "=" * 60,
            "Autonomous Improvement Report",
            "=" * 60,
            f"  Previous Success Rate: {self.previous_success_rate:.1%}",
            f"  Current Success Rate:  {self.current_success_rate:.1%}",
            f"  Improvement Delta:     {self.improvement_delta:+.1%}",
            "",
        ]
        if self.deltas:
            lines.append("Metric Changes:")
            for d in self.deltas:
                arrow = "+" if d.change >= 0 else ""
                lines.append(f"  {d.metric:30s} {d.previous_value:.1%} → {d.current_value:.1%} ({arrow}{d.change:.1%})")
        if self.improvements_made:
            lines.append("")
            lines.append("Improvements Made:")
            for imp in self.improvements_made:
                lines.append(f"  + {imp}")
        if self.recommended_actions:
            lines.append("")
            lines.append("Recommended Actions:")
            for a in self.recommended_actions:
                lines.append(f"  - {a}")
        lines.append("=" * 60)
        return "\n".join(lines)


class ImprovementReportGenerator:
    def __init__(
        self,
        skill_gap_detector: Optional[SkillGapDetector] = None,
        strategy_ranker: Optional[StrategyRanker] = None,
        skill_proposer: Optional[SkillImprovementProposal] = None,
    ):
        self.skill_gap_detector = skill_gap_detector or SkillGapDetector()
        self.strategy_ranker = strategy_ranker or StrategyRanker()
        self.skill_proposer = skill_proposer or SkillImprovementProposal()

    def generate(
        self,
        previous_metrics: Optional[MetricsCollector] = None,
        current_metrics: Optional[MetricsCollector] = None,
    ) -> AutonomousImprovementReport:
        report = AutonomousImprovementReport()

        if previous_metrics and current_metrics:
            report.previous_success_rate = previous_metrics.success_rate
            report.current_success_rate = current_metrics.success_rate
            report.improvement_delta = current_metrics.success_rate - previous_metrics.success_rate

            report.deltas.append(ImprovementDelta(
                metric="success_rate",
                previous_value=previous_metrics.success_rate,
                current_value=current_metrics.success_rate,
                change=current_metrics.success_rate - previous_metrics.success_rate,
            ))

            prev_by_cat = previous_metrics.by_category()
            curr_by_cat = current_metrics.by_category()
            for cat in set(list(prev_by_cat.keys()) + list(curr_by_cat.keys())):
                prev_rate = prev_by_cat.get(cat, {}).get("success_rate", 0)
                curr_rate = curr_by_cat.get(cat, {}).get("success_rate", 0)
                if curr_rate != prev_rate:
                    report.deltas.append(ImprovementDelta(
                        metric=f"{cat}_success_rate",
                        previous_value=prev_rate,
                        current_value=curr_rate,
                        change=curr_rate - prev_rate,
                    ))

        top_gaps = self.skill_gap_detector.get_top_gaps(5)
        if top_gaps:
            proposals = self.skill_proposer.generate_batch(top_gaps)
            report.skill_proposals = proposals
            for p in proposals:
                report.improvements_made.append(
                    f"Detected skill gap: {p['title']} (urgency: {p['urgency']})"
                )

        for cat in ["crypto", "web", "malware", "forensics"]:
            ranked = self.strategy_ranker.get_top_n(cat, 3)
            if ranked:
                report.top_strategies[cat] = ranked

        if report.improvement_delta > 0:
            report.improvements_made.append(
                f"Overall success rate improved by {report.improvement_delta:.1%}"
            )
        elif report.improvement_delta < 0:
            report.recommended_actions.append(
                "Review recent changes — success rate decreased."
            )

        if report.skill_proposals:
            report.recommended_actions.append(
                f"Create {len(report.skill_proposals)} new skill definitions "
                f"to address identified gaps."
            )

        for cat, strategies in report.top_strategies.items():
            if strategies:
                report.recommended_actions.append(
                    f"Apply top strategy for {cat}: {strategies[0]}"
                )

        return report
