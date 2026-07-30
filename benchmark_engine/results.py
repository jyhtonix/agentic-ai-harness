from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class BenchmarkResult:
    challenge_id: str
    category: str
    difficulty: str
    status: str = "unknown"
    flag_result: Optional[str] = None
    execution_time: float = 0.0
    confidence: float = 0.0
    attempts: int = 1
    tools_used: list[str] = field(default_factory=list)
    agents_used: list[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
    failure_category: Optional[str] = None
    verification_details: Optional[dict] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> BenchmarkResult:
        return cls(**d)

    @property
    def solved(self) -> bool:
        return self.status == "solved"

    @property
    def failed(self) -> bool:
        return self.status in ("failed", "timeout", "error")


@dataclass
class BenchmarkReport:
    dataset_name: str = ""
    total_challenges: int = 0
    solved: int = 0
    failed: int = 0
    partial: int = 0
    total_execution_time: float = 0.0
    average_confidence: float = 0.0
    success_rate: float = 0.0
    by_category: dict[str, dict] = field(default_factory=dict)
    by_difficulty: dict[str, dict] = field(default_factory=dict)
    agent_performance: dict[str, dict] = field(default_factory=dict)
    tool_usage: dict[str, int] = field(default_factory=dict)
    failure_breakdown: dict[str, int] = field(default_factory=dict)
    weakest_area: str = ""
    recommendations: list[str] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dataclass_fields__.items():
            val = getattr(self, k)
            if hasattr(val, "to_dict"):
                d[k] = val.to_dict()
            elif isinstance(val, list) and val and hasattr(val[0], "to_dict"):
                d[k] = [x.to_dict() for x in val]
            else:
                d[k] = val
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def summary_table(self) -> str:
        lines = [
            "=" * 60,
            f"CTF Benchmark Report: {self.dataset_name}",
            "=" * 60,
            f"  Total Challenges:  {self.total_challenges}",
            f"  Solved:            {self.solved}",
            f"  Failed:            {self.failed}",
            f"  Partial:           {self.partial}",
            f"  Success Rate:      {self.success_rate:.1%}",
            f"  Avg Confidence:    {self.average_confidence:.2f}",
            f"  Total Time:        {self.total_execution_time:.1f}s",
            "",
            "By Category:",
        ]
        for cat, stats in sorted(self.by_category.items()):
            rate = stats.get("success_rate", 0)
            lines.append(f"  {cat:15s}  {rate:.1%}  ({stats.get('solved', 0)}/{stats.get('total', 0)})")
        lines.append("")
        lines.append("By Difficulty:")
        for diff, stats in sorted(self.by_difficulty.items()):
            rate = stats.get("success_rate", 0)
            lines.append(f"  {diff:15s}  {rate:.1%}  ({stats.get('solved', 0)}/{stats.get('total', 0)})")
        if self.weakest_area:
            lines.append("")
            lines.append(f"Weakest Area: {self.weakest_area}")
        if self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for r in self.recommendations:
                lines.append(f"  - {r}")
        lines.append("=" * 60)
        return "\n".join(lines)
