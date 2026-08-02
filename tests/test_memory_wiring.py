"""Tests for Phase 1 memory wiring — active CTF learning loop.

Covers:
  - CTFEpisode capture from supervisor output
  - Rich episodic storage in SolutionMemory / FailureMemory
  - MemoryService retrieval and context formatting
  - Planner memory injection
  - BenchmarkRunner learning wiring
  - API challenge run learning capture
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from memory.episode import CTFEpisode, build_episode_from_supervisor_output
from memory.service import MemoryService
from memory.solutions import SolutionMemory
from memory.failures import FailureMemory
from memory.strategies import StrategyMemory
from skills_engine.planner import SkillPlanner
from benchmark_engine.runner import BenchmarkRunner
from benchmark_engine.results import BenchmarkResult

from challenges_engine.loader import ChallengeLoader


# ===================================================================
# Fixtures
# ===================================================================

def make_solved_output() -> dict:
    return {
        "request": "Decrypt the RSA ciphertext and recover the flag",
        "analysis": "RSA challenge — check for small exponent",
        "plan": [
            {"agent": "crypto_agent", "task": "Analyse RSA params", "depends_on": []},
            {"agent": "crypto_agent", "task": "Decrypt and verify", "depends_on": [0]},
        ],
        "agent_results": [
            {"step": 0, "agent": "crypto_agent", "status": "completed",
             "response": "Used python to factor n with sympy. Found flag: CTF{rsa_solved}"},
        ],
        "verification": {"status": "passed", "confidence_score": 0.9, "findings": []},
        "learning_report": {
            "challenge_id": "rsa_001",
            "difficulty_estimate": "medium",
            "tools_used": ["python"],
            "skills_used": [{"name": "rsa-fundamentals", "category": "crypto"}],
        },
        "flag_verification": {"status": "PASS", "method": "exact_flag", "student_flag": "CTF{rsa_solved}"},
        "challenge": {"name": "RSA Basic", "category": "crypto", "difficulty": "medium"},
        "final_response": "Factored n with sympy and recovered the flag.",
    }


def make_failed_output() -> dict:
    out = make_solved_output()
    out["agent_results"] = [
        {"step": 0, "agent": "crypto_agent", "status": "failed",
         "response": "Brute force too slow, gave up"},
    ]
    out["verification"] = {"status": "failed", "confidence_score": 0.2, "findings": []}
    out["flag_verification"] = {"status": "FAIL", "student_flag": ""}
    out["final_response"] = "Failed to recover the flag."
    return out


# ===================================================================
# CTFEpisode capture
# ===================================================================

class TestCTFEpisodeCapture:
    def test_solved_episode_fields(self):
        ep = build_episode_from_supervisor_output(make_solved_output())
        assert ep is not None
        assert ep.status == "solved"
        assert ep.solved is True
        assert ep.category == "crypto"
        assert "rsa-fundamentals" in ep.skills_selected
        assert "python" in ep.tools_used
        assert len(ep.initial_plan) == 2
        assert any("python" in c for c in ep.actions_commands)
        assert ep.flag_result == "PASS"
        assert ep.confidence == 0.9

    def test_failed_episode_fields(self):
        ep = build_episode_from_supervisor_output(make_failed_output())
        assert ep is not None
        assert ep.status == "failed"
        assert ep.solved is False
        assert ep.flag_result == "FAIL"

    def test_none_output_returns_none(self):
        assert build_episode_from_supervisor_output(None) is None
        assert build_episode_from_supervisor_output({}) is None


# ===================================================================
# Rich episodic storage
# ===================================================================

class TestRichEpisodicStorage:
    def test_solution_episode_fields_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SolutionMemory(storage_dir=td)
            mem.record(
                "rsa_001", "crypto", "medium", "small exponent attack",
                ["python"], ["crypto_agent"], True,
                description="Decrypt RSA",
                successful_techniques=["Factor n with sympy"],
                actions_commands=["python solve.py"],
                final_solution_reasoning="Found small exponent",
            )
            sols = mem.get_solutions(category="crypto")
            assert len(sols) == 1
            assert sols[0]["successful_techniques"] == ["Factor n with sympy"]
            assert sols[0]["actions_commands"] == ["python solve.py"]
            assert sols[0]["description"] == "Decrypt RSA"

    def test_failure_episode_fields_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FailureMemory(storage_dir=td)
            mem.record(
                "rsa_002", "crypto", "brute force slow", "insufficient_reasoning",
                recommendation="Try factorisation",
                description="RSA with large key",
                failed_approaches=["brute force"],
            )
            fails = mem.get_failures(category="crypto")
            assert len(fails) == 1
            assert fails[0]["failed_approaches"] == ["brute force"]
            assert fails[0]["description"] == "RSA with large key"

    def test_solution_relevance_ranking(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SolutionMemory(storage_dir=td)
            mem.record("c1", "crypto", "m", "padding oracle", ["python"], ["a"], True,
                       description="AES CBC padding oracle decrypt")
            mem.record("c2", "crypto", "m", "small exponent", ["python"], ["a"], True,
                       description="RSA small exponent attack")
            mem.record("c3", "crypto", "m", "brute force", ["python"], ["a"], True,
                       description="XOR brute force")
            relevant = mem.get_relevant("crypto", "RSA small exponent factor n", limit=2)
            assert relevant
            assert "small exponent" in relevant[0]["approach"]


# ===================================================================
# MemoryService
# ===================================================================

class TestMemoryService:
    def test_record_and_retrieve(self):
        with tempfile.TemporaryDirectory() as td:
            service = MemoryService(memory_dir=td)
            service.record_supervisor_output(make_solved_output())

            context = service.retrieve_context("crypto", "RSA decrypt flag")
            assert context["solutions"]
            assert context["solutions"][0]["category"] == "crypto"

            formatted = service.format_context("crypto", "RSA decrypt flag")
            assert "Prior successful solutions" in formatted
            assert "Prior failures" in formatted or "Proven strategies" in formatted or "Approaches to avoid" in formatted

    def test_record_failure_flow(self):
        with tempfile.TemporaryDirectory() as td:
            service = MemoryService(memory_dir=td)
            entry = service.record_supervisor_output(make_failed_output())
            assert entry is not None
            assert entry["status"] == "failed"

    def test_format_context_empty(self):
        with tempfile.TemporaryDirectory() as td:
            service = MemoryService(memory_dir=td)
            formatted = service.format_context("web", "sql injection")
            assert formatted == ""

    def test_summary(self):
        with tempfile.TemporaryDirectory() as td:
            service = MemoryService(memory_dir=td)
            service.record_supervisor_output(make_solved_output())
            summary = service.get_summary()
            assert summary["solutions_stored"] == 1


# ===================================================================
# Planner memory injection
# ===================================================================

class TestPlannerMemoryInjection:
    @pytest.mark.asyncio
    async def test_planner_includes_memory_context(self):
        class SimpleResponse:
            def __init__(self, content):
                self.content = content

        class FakeLLM:
            def __init__(self):
                self.last_prompt = ""

            async def chat(self, messages, **kwargs):
                self.last_prompt = messages[0]["content"]
                return SimpleResponse('{"analysis": "x", "steps": []}')

        class FakeRegistry:
            def list_agents(self):
                return {"crypto_agent": {}}

        with tempfile.TemporaryDirectory() as td:
            service = MemoryService(memory_dir=td)
            service.record_supervisor_output(make_solved_output())

            llm = FakeLLM()
            planner = SkillPlanner(llm=llm, registry=FakeRegistry(), memory_service=service)
            await planner.create_plan("Decrypt the RSA ciphertext", category="crypto")
            assert "Prior successful solutions" in llm.last_prompt


# ===================================================================
# BenchmarkRunner learning wiring
# ===================================================================

class TestBenchmarkRunnerLearning:
    @pytest.mark.asyncio
    async def test_runner_records_learning(self):
        with tempfile.TemporaryDirectory() as td:
            service = MemoryService(memory_dir=td)
            loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
            supervisor = AsyncMock(return_value=make_solved_output())
            runner = BenchmarkRunner(
                challenge_loader=loader,
                supervisor_factory=supervisor,
                learning_service=service,
            )
            result = await runner.run_challenge("crypto_basic_001")
            assert result.status == "solved"
            summary = service.get_summary()
            assert summary["solutions_stored"] >= 1

    @pytest.mark.asyncio
    async def test_runner_no_learning_service_noop(self):
        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
        supervisor = AsyncMock(return_value=make_solved_output())
        runner = BenchmarkRunner(
            challenge_loader=loader,
            supervisor_factory=supervisor,
        )
        result = await runner.run_challenge("crypto_basic_001")
        assert result.status == "solved"

    @pytest.mark.asyncio
    async def test_runner_records_failure_learning(self):
        with tempfile.TemporaryDirectory() as td:
            service = MemoryService(memory_dir=td)
            loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
            supervisor = AsyncMock(return_value=make_failed_output())
            runner = BenchmarkRunner(
                challenge_loader=loader,
                supervisor_factory=supervisor,
                learning_service=service,
            )
            result = await runner.run_challenge("crypto_basic_001")
            assert result.status == "failed"
            summary = service.get_summary()
            assert summary["failures_stored"] >= 1
