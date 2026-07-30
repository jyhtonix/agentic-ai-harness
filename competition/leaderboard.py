"""Leaderboard for CTF competition."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from competition.scoring import Scorer, ScoreEntry

logger = logging.getLogger("competition.leaderboard")


class Leaderboard:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or (Path.cwd() / "competition" / "results"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[ScoreEntry] = []
        self._scorer = Scorer()
        self._load()

    def record(self, entry: ScoreEntry) -> None:
        for existing in self._entries:
            if existing.team_name == entry.team_name:
                self._entries.remove(existing)
                break
        self._entries.append(entry)
        self._save()

    def get_rankings(self) -> list[dict]:
        ranked = self._scorer.rank_entries(self._entries)
        return [
            {
                "rank": i + 1,
                **entry.to_dict(),
            }
            for i, entry in enumerate(ranked)
        ]

    def get_team(self, team_name: str) -> Optional[ScoreEntry]:
        for entry in self._entries:
            if entry.team_name == team_name:
                return entry
        return None

    def clear(self) -> None:
        self._entries.clear()
        self._save()

    def _save(self) -> None:
        path = self.storage_dir / "leaderboard.json"
        with open(path, "w") as f:
            json.dump([e.to_dict() for e in self._entries], f, indent=2)

    def _load(self) -> None:
        path = self.storage_dir / "leaderboard.json"
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                for d in data:
                    entry = ScoreEntry(
                        team_name=d["team_name"],
                        total_score=d["total_score"],
                        solved=d["solved"],
                        total_challenges=d["total_challenges"],
                        total_time=d["total_time"],
                        points_per_challenge=d.get("points_per_challenge", {}),
                    )
                    self._entries.append(entry)
            except (json.JSONDecodeError, OSError, KeyError):
                self._entries = []
