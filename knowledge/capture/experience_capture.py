"""Experience Capture seam — record a solved challenge into memory.

The single entry point for turning a *completed* challenge into durable
memory, regardless of how it was solved:

  * externally (an exploit script, ad-hoc socket session)
  * manually (a written write-up)
  * by the harness supervisor (already covered by
    MemoryService.record_supervisor_output, which is left untouched)

The seam reuses the existing building blocks — CTFEpisode schema,
SolutionMemory.record(), StrategyMemory.record(), StrategyMemory.record_failed()
— and mirrors the persistence that the manual knowledge importer already
performs, so the rich approach text and source metadata are preserved.

No new LLM, no vector DB, no changes to the solving flow.
"""

from __future__ import annotations

import logging
from typing import Optional

from memory.service import MemoryService
from memory.solutions import SolutionMemory
from memory.strategies import StrategyMemory
from knowledge.capture.solve_summary import CaptureSummary

logger = logging.getLogger("knowledge.capture.experience_capture")


def capture_solve(
    summary: CaptureSummary,
    memory_service: Optional[MemoryService] = None,
    solution_memory: Optional[SolutionMemory] = None,
    strategy_memory: Optional[StrategyMemory] = None,
    source: Optional[str] = None,
    imported_by: Optional[str] = None,
    source_filename: Optional[str] = None,
) -> dict:
    """Persist a solved challenge into memory.

    Provide either a memory_service, or solution_memory + strategy_memory
    directly (as the manual loader does). Overrides (source, imported_by,
    source_filename) are applied on top of the summary so callers can tag
    provenance at the call site without mutating the summary. Dedup is by
    normalized challenge_id.

    Returns a report dict: status ("imported" | "duplicate"),
    challenge_id, and the learner entry when imported.
    """
    if memory_service is None and (solution_memory is None or strategy_memory is None):
        service = MemoryService()
    elif memory_service is not None:
        service = memory_service
    else:
        service = MemoryService(
            solution_memory=solution_memory, strategy_memory=strategy_memory
        )
    solution_memory = solution_memory or service.solution_memory
    strategy_memory = strategy_memory or service.strategy_memory
    challenge_id = (summary.challenge_id or "").strip().lower()

    existing = {
        (s.get("challenge_id") or "").strip().lower()
        for s in solution_memory.get_solutions()
    }
    if challenge_id in existing:
        logger.info("Challenge '%s' already in memory, skipping", summary.challenge_id)
        return {"status": "duplicate", "challenge_id": summary.challenge_id}

    if source:
        summary.source = source
    if imported_by:
        summary.imported_by = imported_by
    if source_filename:
        summary.source_filename = source_filename

    episode = summary.to_episode()
    techniques = summary.successful_techniques or []
    failed = [f for f in (summary.failed_approaches or []) if f]

    solution_memory.record(
        challenge_id=episode.challenge_id,
        category=episode.category,
        difficulty=episode.difficulty,
        approach=summary.approach or episode.challenge_id,
        tools_used=episode.tools_used,
        agents_used=episode.agents_used or ["manual_capture"],
        success=True,
        description=episode.description,
        skills_selected=episode.skills_selected,
        actions_commands=episode.tools_used,
        successful_techniques=techniques,
        failed_approaches=failed,
        final_solution_reasoning=episode.final_solution_reasoning,
        flag_result=episode.flag_result,
        confidence=episode.confidence,
        source_metadata=summary.source_metadata(),
    )

    if summary.approach:
        strategy_memory.record(
            episode.category,
            f"{episode.challenge_id}: {summary.approach[:120]}",
            confidence=episode.confidence,
        )
    for failed_approach in failed:
        strategy_memory.record_failed(
            episode.category, failed_approach, failure_reason=failed_approach
        )

    logger.info(
        "Captured solve for '%s' (%s) into memory [%s]",
        summary.challenge_id,
        summary.category,
        summary.source,
    )
    return {
        "status": "imported",
        "challenge_id": summary.challenge_id,
        "category": summary.category,
        "entry": episode.to_dict(),
    }
