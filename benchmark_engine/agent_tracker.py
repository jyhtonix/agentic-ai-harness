from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentStats:
    challenges_attempted: int = 0
    solved: int = 0
    failed: int = 0
    total_confidence: float = 0.0
    categories: set[str] = field(default_factory=set)
    tools_used: set[str] = field(default_factory=set)

    @property
    def success_rate(self) -> float:
        if self.challenges_attempted == 0:
            return 0.0
        return round(self.solved / self.challenges_attempted, 3)

    @property
    def average_confidence(self) -> float:
        if self.challenges_attempted == 0:
            return 0.0
        return round(self.total_confidence / self.challenges_attempted, 3)

    def to_dict(self) -> dict:
        return {
            "challenges_attempted": self.challenges_attempted,
            "solved": self.solved,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "average_confidence": self.average_confidence,
            "categories": sorted(self.categories),
            "tools_used": sorted(self.tools_used),
        }


class AgentMetricsTracker:
    def __init__(self):
        self._agents: dict[str, AgentStats] = {}

    def record(self, agent_name: str, solved: bool, confidence: float = 0.0,
               category: str = "", tools_used: Optional[list[str]] = None) -> None:
        if agent_name not in self._agents:
            self._agents[agent_name] = AgentStats()
        stats = self._agents[agent_name]
        stats.challenges_attempted += 1
        if solved:
            stats.solved += 1
        else:
            stats.failed += 1
        stats.total_confidence += confidence
        if category:
            stats.categories.add(category)
        if tools_used:
            stats.tools_used.update(tools_used)

    def get(self, agent_name: str) -> Optional[AgentStats]:
        return self._agents.get(agent_name)

    def all(self) -> dict[str, dict]:
        return {name: stats.to_dict() for name, stats in self._agents.items()}

    @property
    def total_agents(self) -> int:
        return len(self._agents)

    def get_weakest(self) -> Optional[str]:
        if not self._agents:
            return None
        worst = min(self._agents.items(), key=lambda x: x[1].success_rate)
        return worst[0] if worst[1].challenges_attempted > 0 else None

    def get_strongest(self) -> Optional[str]:
        if not self._agents:
            return None
        best = max(self._agents.items(), key=lambda x: x[1].success_rate)
        return best[0] if best[1].challenges_attempted > 0 else None

    def clear(self) -> None:
        self._agents.clear()
