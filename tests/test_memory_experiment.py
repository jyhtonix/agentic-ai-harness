"""Tests for the memory A/B experiment engine (benchmark_engine.memory_experiment).

Uses a fake supervisor so the orchestration logic is verified deterministically.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from benchmark_engine.memory_experiment import (
    MemoryExperiment,
    MemoryExperimentReport,
    _BoundSupervisor,
)
from benchmark_engine.history import BenchmarkHistory
from challenges_engine.loader import ChallengeLoader


# ===================================================================
# Helpers
# ===================================================================

def make_output(challenge_id: str, solved: bool, tools=None, category: str = "misc") -> dict:
    tools = tools or ["python"]
    flag_status = "PASS" if solved else "FAIL"
    status = "completed" if solved else "failed"
    return {
        "request": f"Solve {challenge_id}",
        "analysis": f"Analyse {challenge_id}",
        "plan": [
            {"agent": "security_agent", "task": "Analyse", "depends_on": []},
            {"agent": "coder", "task": "Recover flag", "depends_on": [0]},
        ],
        "agent_results": [
            {"step": 0, "agent": "security_agent", "status": "completed",
             "response": "Analysed the artefact and found a candidate approach"},
            {"step": 1, "agent": "coder", "status": status,
             "response": ("Recovered the flag: CTF{abc}" if solved else "Gave up")},
        ],
        "verification": {"status": "passed", "confidence_score": 0.8 if solved else 0.2,
                         "findings": []},
        "learning_report": {
            "challenge_id": challenge_id,
            "difficulty_estimate": "beginner",
            "tools_used": tools,
            "skills_used": [{"name": "basic-analysis", "category": "misc"}],
        },
        "flag_verification": {"status": flag_status, "student_flag": "CTF{abc}" if solved else ""},
        "challenge": {"name": challenge_id, "category": category, "difficulty": "beginner"},
        "final_response": "Done." if solved else "Failed.",
    }


class FakeSupervisor:
    """Fake supervisor — solves a challenge only when memory is present
    (except crypto, which it always solves). Simulates memory-enabled solving."""

    def __init__(self, memory_enabled: bool):
        self.memory_enabled = memory_enabled
        self.calls = 0

    async def run(self, request: str, challenge_id: str = "") -> dict:
        self.calls += 1
        solved = self.memory_enabled or challenge_id == "crypto_basic_001"
        category = "cryptography" if challenge_id == "crypto_basic_001" else "malware"
        return make_output(challenge_id, solved=solved, category=category)


def make_builder():
    async def build(memory_service):
        return FakeSupervisor(memory_enabled=memory_service is not None)
    return build


def make_experiment(challenge_ids, builder, memory_dir, history_dir=None):
    history = BenchmarkHistory(storage_dir=history_dir or (memory_dir + "_history"))
    return MemoryExperiment(
        challenge_ids=challenge_ids,
        supervisor_builder=builder,
        loader=ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges")),
        memory_dir=memory_dir,
        dataset_name="test_ab",
        history=history,
    )


# ===================================================================
# _BoundSupervisor
# ===================================================================

class TestBoundSupervisor:
    @pytest.mark.asyncio
    async def test_captures_output(self):
        sup = FakeSupervisor("cold")
        bound = _BoundSupervisor(sup, "crypto_basic_001")
        out = await bound.run()
        assert out["flag_verification"]["status"] == "PASS"
        assert bound.output is out


# ===================================================================
# MemoryExperiment
# ===================================================================

class TestMemoryExperiment:
    @pytest.mark.asyncio
    async def test_cold_and_warm_passes_run(self):
        with tempfile.TemporaryDirectory() as td:
            exp = make_experiment(
                ["crypto_basic_001", "malware_basic_001"],
                make_builder(),
                td,
            )
            report = await exp.run()

            assert isinstance(report, MemoryExperimentReport)
            assert len(exp.cold_runs) == 2
            assert len(exp.warm_runs) == 2
            assert report.cold_summary is not None
            assert report.warm_summary is not None

    @pytest.mark.asyncio
    async def test_warm_pass_shows_improvement_when_memory_helps(self):
        # Cold supervisor solves only crypto; warm supervisor solves everything.
        with tempfile.TemporaryDirectory() as td:
            exp = make_experiment(
                ["crypto_basic_001", "malware_basic_001"],
                make_builder(),
                td,
            )
            report = await exp.run()

            assert report.cold_summary.solved == 1
            assert report.warm_summary.solved == 2
            assert report.warm_summary.success_rate > report.cold_summary.success_rate
            assert report.improvement

    @pytest.mark.asyncio
    async def test_memory_seeded_from_cold_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            exp = make_experiment(
                ["crypto_basic_001"],
                make_builder(),
                td,
            )
            report = await exp.run()
            assert report.memory_summary["solutions_stored"] >= 1

    @pytest.mark.asyncio
    async def test_recovered_context_populated(self):
        with tempfile.TemporaryDirectory() as td:
            exp = make_experiment(
                ["crypto_basic_001"],
                make_builder(),
                td,
            )
            report = await exp.run()
            assert report.comparisons
            assert "Prior successful solutions" in report.comparisons[0].recovered_context

    @pytest.mark.asyncio
    async def test_summary_table_contains_both_modes(self):
        with tempfile.TemporaryDirectory() as td:
            exp = make_experiment(
                ["crypto_basic_001"],
                make_builder(),
                td,
            )
            report = await exp.run()
            table = report.summary_table()
            assert "Cold (no memory)" in table
            assert "Warm (memory)" in table
            assert "Improvement" in table

    @pytest.mark.asyncio
    async def test_unknown_challenge_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            exp = make_experiment(
                ["nonexistent_challenge_xyz", "crypto_basic_001"],
                make_builder(),
                td,
            )
            report = await exp.run()
            assert len(exp.cold_runs) == 1
            assert len(exp.warm_runs) == 1
