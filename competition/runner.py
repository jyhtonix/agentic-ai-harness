"""CompetitionRunner — runs CTF competition simulations."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Callable, Awaitable

from benchmark_engine.results import BenchmarkResult
from competition.scoring import Scorer
from competition.leaderboard import Leaderboard

logger = logging.getLogger("competition.runner")

ChallengeRunner = Callable[[str], Awaitable[BenchmarkResult]]

DIFFICULTY_POINTS = {
    "beginner": 100,
    "easy": 100,
    "medium": 300,
    "hard": 500,
    "insane": 1000,
}


class CompetitionConfig:
    def __init__(self, name: str = "CTF Competition",
                 time_limit_hours: int = 4,
                 max_attempts_per_challenge: int = 3,
                 point_decay: bool = True):
        self.name = name
        self.time_limit_hours = time_limit_hours
        self.max_attempts_per_challenge = max_attempts_per_challenge
        self.point_decay = point_decay


class CompetitionRunner:
    def __init__(
        self,
        challenge_runner: Optional[ChallengeRunner] = None,
        config: Optional[CompetitionConfig] = None,
        scorer: Optional[Scorer] = None,
        leaderboard: Optional[Leaderboard] = None,
    ):
        self.challenge_runner = challenge_runner
        self.config = config or CompetitionConfig()
        self.scorer = scorer or Scorer()
        self.leaderboard = leaderboard or Leaderboard()
        self._results: dict[str, list[BenchmarkResult]] = {}

    async def run_competition(self, challenge_ids: list[str],
                              team_name: str = "default_team") -> dict:
        logger.info("Starting competition: %s (%d challenges, %d hour limit)",
                     self.config.name, len(challenge_ids), self.config.time_limit_hours)

        start_time = time.time()
        time_limit_seconds = self.config.time_limit_hours * 3600

        results_by_challenge: list[BenchmarkResult] = []
        total_score = 0

        for cid in challenge_ids:
            elapsed = time.time() - start_time
            if elapsed > time_limit_seconds:
                logger.warning("Time limit exceeded. Stopping competition.")
                break

            for attempt in range(1, self.config.max_attempts_per_challenge + 1):
                logger.info("Challenge %s attempt %d/%d", cid, attempt,
                            self.config.max_attempts_per_challenge)
                result = await self.challenge_runner(cid)
                result.attempts = attempt

                if result.solved:
                    base_points = DIFFICULTY_POINTS.get(result.difficulty, 100)
                    if self.config.point_decay:
                        decay = 1.0 - (attempt - 1) * 0.2
                        points = int(base_points * max(decay, 0.4))
                    else:
                        points = base_points
                    existing = getattr(result, 'metadata', None) or {}
                    metadata = dict(existing)
                    metadata["points"] = points
                    result.metadata = metadata
                    total_score += points
                    results_by_challenge.append(result)
                    logger.info("Solved %s on attempt %d for %d points", cid, attempt, points)
                    break
            else:
                results_by_challenge.append(result)

        elapsed_time = round(time.time() - start_time, 1)
        score_entry = self.scorer.calculate_score(
            team_name=team_name,
            results=results_by_challenge,
            total_time=elapsed_time,
        )

        self.leaderboard.record(score_entry)
        self._results[team_name] = results_by_challenge

        return {
            "competition_name": self.config.name,
            "team": team_name,
            "challenges_total": len(challenge_ids),
            "challenges_solved": score_entry.solved,
            "total_score": score_entry.total_score,
            "time_elapsed": elapsed_time,
            "time_limit_hours": self.config.time_limit_hours,
            "results": [r.to_dict() for r in results_by_challenge],
            "leaderboard": self.leaderboard.get_rankings(),
        }
