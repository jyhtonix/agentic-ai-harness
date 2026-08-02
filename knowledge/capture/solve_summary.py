"""CaptureSummary — the structured unit of a solved challenge.

A CaptureSummary is the input contract for the Experience Capture seam. It
carries everything a successful solve produces (technique, evidence,
reasoning, flag) so that ANY source — a manual write-up, an external exploit
script, or a future automated learner — can feed a solve into the memory
pipeline through a single entry point (capture_solve).

It maps onto the existing CTFEpisode schema via to_episode(), so the rest of
the pipeline (learner, SolutionMemory, StrategyMemory) is reused unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from memory.episode import CTFEpisode


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CaptureSummary:
    challenge_id: str
    category: str
    difficulty: str = "unknown"
    description: str = ""
    approach: str = ""
    tools_used: list = field(default_factory=list)
    agents_used: list = field(default_factory=lambda: ["manual_capture"])
    skills_selected: list = field(default_factory=list)
    successful_techniques: list = field(default_factory=list)
    failed_approaches: list = field(default_factory=list)
    final_solution_reasoning: str = ""
    flag_result: Optional[str] = None
    confidence: float = 0.9
    execution_time: float = 0.0
    attempts: int = 1

    source: str = "external_script"
    imported_by: str = "unknown"
    source_filename: Optional[str] = None

    def to_episode(self) -> CTFEpisode:
        """Map this summary onto the existing CTFEpisode schema (status solved)."""
        return CTFEpisode(
            challenge_id=self.challenge_id,
            category=self.category,
            difficulty=self.difficulty,
            status="solved",
            description=self.description,
            agents_used=self.agents_used or ["manual_capture"],
            skills_selected=self.skills_selected,
            tools_used=self.tools_used,
            successful_techniques=self.successful_techniques,
            failed_approaches=self.failed_approaches,
            final_solution_reasoning=self.final_solution_reasoning
            or self.approach,
            flag_result=self.flag_result,
            confidence=self.confidence,
            execution_time=self.execution_time,
            attempts=self.attempts,
        )

    def source_metadata(self) -> dict:
        """Tag this record so its provenance is auditable in the stores."""
        meta = {
            "source": self.source,
            "imported_by": self.imported_by,
            "captured_at": _now(),
        }
        if self.source_filename:
            meta["filename"] = self.source_filename
        return meta

    @classmethod
    def from_dict(cls, data: dict) -> "CaptureSummary":
        """Build a summary from a plain dict (e.g. JSON from an exploit script)."""
        allowed = set(cls.__dataclass_fields__.keys())
        return cls(**{k: v for k, v in data.items() if k in allowed})
