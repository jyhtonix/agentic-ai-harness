"""Scoring system for CTF competition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from benchmark_engine.results import BenchmarkResult


@dataclass
class ScoreEntry:
    team_name: str
    total_score: int = 0
    solved: int = 0
    total_challenges: int = 0
    total_time: float = 0.0
    points_per_challenge: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "team_name": self.team_name,
            "total_score": self.total_score,
            "solved": self.solved,
            "total_challenges": self.total_challenges,
            "total_time": round(self.total_time, 1),
            "points_per_challenge": dict(self.points_per_challenge),
        }


class Scorer:
    def calculate_score(self, team_name: str, results: list[BenchmarkResult],
                        total_time: float = 0.0) -> ScoreEntry:
        entry = ScoreEntry(
            team_name=team_name,
            total_challenges=len(results),
            total_time=total_time,
        )

        for r in results:
            if r.solved:
                entry.solved += 1
                points = 0
                r_meta = getattr(r, 'metadata', None) or {}
                if isinstance(r_meta, dict):
                    points = r_meta.get("points", 0)
                entry.total_score += points
                entry.points_per_challenge[r.challenge_id] = points

        return entry

    def rank_entries(self, entries: list[ScoreEntry]) -> list[ScoreEntry]:
        return sorted(
            entries,
            key=lambda e: (-e.total_score, e.total_time),
        )
