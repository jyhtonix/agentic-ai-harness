"""Tests for the CTF Benchmarking & Autonomous Improvement Framework.

Covers:
  - BenchmarkResult model
  - MetricsCollector aggregation and breakdowns
  - BenchmarkRunner with fake supervisor
  - FailureAnalyzer classification
  - RetryController strategy management
  - AgentMetricsTracker per-agent stats
  - StrategyMemory persistence
  - FailureMemory recording
  - SolutionMemory recording
  - Evaluator report generation
  - DatasetLoader
  - SupervisorAgent backward compatibility
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from benchmark_engine.results import BenchmarkResult, BenchmarkReport
from benchmark_engine.metrics import MetricsCollector
from benchmark_engine.runner import BenchmarkRunner
from benchmark_engine.failure import FailureAnalyzer
from benchmark_engine.retry import RetryController
from benchmark_engine.agent_tracker import AgentMetricsTracker
from benchmark_engine.evaluator import Evaluator
from benchmark_engine.history import BenchmarkHistory
from benchmark_engine.dataset import DatasetLoader
from memory.strategies import StrategyMemory
from memory.failures import FailureMemory
from memory.solutions import SolutionMemory

from challenges_engine.loader import ChallengeLoader


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def sample_results() -> list[BenchmarkResult]:
    return [
        BenchmarkResult(
            challenge_id="crypto_001", category="crypto", difficulty="medium",
            status="solved", flag_result="PASS", execution_time=5.2,
            confidence=0.85, tools_used=["python"], agents_used=["crypto_agent"],
        ),
        BenchmarkResult(
            challenge_id="web_001", category="web", difficulty="medium",
            status="solved", flag_result="PASS", execution_time=3.1,
            confidence=0.78, tools_used=["curl"], agents_used=["web_agent"],
        ),
        BenchmarkResult(
            challenge_id="malware_001", category="malware", difficulty="hard",
            status="failed", flag_result="FAIL", execution_time=10.0,
            confidence=0.3, failure_reason="Insufficient skill coverage",
            failure_category="missing_skill", tools_used=["file"],
            agents_used=["malware_agent"],
        ),
        BenchmarkResult(
            challenge_id="forensics_001", category="forensics", difficulty="medium",
            status="solved", flag_result="PASS", execution_time=7.8,
            confidence=0.92, tools_used=["exiftool", "strings"],
            agents_used=["forensics_agent"],
        ),
    ]


def make_fake_supervisor_result(solved: bool = True) -> dict:
    return {
        "request": "Solve the challenge",
        "analysis": "Test analysis",
        "plan": [{"agent": "analyst", "task": "analyze", "depends_on": []}],
        "agent_results": [{"agent": "analyst", "status": "completed", "response": "CTF{flag}"}],
        "verification": {"status": "PASS", "confidence_score": 0.9, "findings": []} if solved else None,
        "learning_report": {"tools_used": ["python", "curl"], "challenge_id": "test", "difficulty_estimate": "medium", "learning_objectives": [], "skills_used": [], "skills_mastered": [], "skills_needing_improvement": [], "recommendations": [], "student_report": "", "instructor_summary": ""},
        "flag_verification": {"status": "PASS", "method": "exact_flag", "detail": "Matched", "student_flag": "CTF{flag}"} if solved else {"status": "FAIL", "method": "exact_flag", "detail": "No match", "student_flag": ""},
        "challenge": {"name": "Test", "category": "crypto", "difficulty": "medium"},
        "team_coordination": None,
        "final_response": "Challenge solved." if solved else "Failed.",
    }


# ===================================================================
# BenchmarkResult
# ===================================================================

class TestBenchmarkResult:
    def test_creation(self):
        r = BenchmarkResult(
            challenge_id="crypto_001", category="crypto", difficulty="medium",
            status="solved", flag_result="PASS",
        )
        assert r.challenge_id == "crypto_001"
        assert r.solved is True
        assert r.failed is False

    def test_failed_status(self):
        r = BenchmarkResult(
            challenge_id="web_001", category="web", difficulty="hard",
            status="failed", flag_result="FAIL",
        )
        assert r.solved is False
        assert r.failed is True

    def test_to_dict(self):
        r = BenchmarkResult(challenge_id="x", category="c", difficulty="d", status="solved", execution_time=1.0)
        d = r.to_dict()
        assert d["challenge_id"] == "x"
        assert d["status"] == "solved"
        assert d["execution_time"] == 1.0

    def test_from_dict(self):
        d = {"challenge_id": "x", "category": "c", "difficulty": "d", "status": "solved"}
        r = BenchmarkResult.from_dict(d)
        assert r.challenge_id == "x"

    def test_timeout_is_failed(self):
        r = BenchmarkResult(challenge_id="x", category="c", difficulty="d", status="timeout")
        assert r.failed is True


# ===================================================================
# MetricsCollector
# ===================================================================

class TestMetricsCollector:
    def test_empty_collector(self):
        mc = MetricsCollector()
        assert mc.total == 0
        assert mc.success_rate == 0.0

    def test_record(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        assert mc.total == 4
        assert mc.solved == 3
        assert mc.failed == 1
        assert mc.success_rate == 0.75

    def test_by_category(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        cats = mc.by_category()
        assert "crypto" in cats
        assert cats["crypto"]["solved"] == 1
        assert cats["malware"]["solved"] == 0

    def test_by_difficulty(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        diffs = mc.by_difficulty()
        assert "medium" in diffs
        assert diffs["medium"]["solved"] == 3

    def test_agent_metrics(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        agents = mc.agent_metrics()
        assert "crypto_agent" in agents
        assert agents["crypto_agent"]["solved"] == 1

    def test_tool_usage(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        usage = mc.tool_usage()
        assert "python" in usage
        assert usage["python"] == 1

    def test_failure_breakdown(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        fb = mc.failure_breakdown()
        assert "missing_skill" in fb

    def test_timer(self):
        mc = MetricsCollector()
        mc.start_timer()
        import time
        time.sleep(0.01)
        elapsed = mc.elapsed()
        assert elapsed > 0

    def test_clear(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        mc.clear()
        assert mc.total == 0


# ===================================================================
# BenchmarkRunner
# ===================================================================

class TestBenchmarkRunner:
    @pytest.mark.asyncio
    async def test_run_with_fake_supervisor(self):
        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
        supervisor = AsyncMock(return_value=make_fake_supervisor_result(solved=True))
        runner = BenchmarkRunner(
            challenge_loader=loader,
            supervisor_factory=supervisor,
        )
        result = await runner.run_challenge("crypto_basic_001")
        assert result is not None
        assert result.status == "solved"

    @pytest.mark.asyncio
    async def test_run_unknown_challenge(self):
        runner = BenchmarkRunner()
        result = await runner.run_challenge("nonexistent_challenge_xyz")
        assert result.status == "error"
        assert "not found" in (result.failure_reason or "")

    @pytest.mark.asyncio
    async def test_run_failed_challenge(self):
        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
        supervisor = AsyncMock(return_value=make_fake_supervisor_result(solved=False))
        runner = BenchmarkRunner(
            challenge_loader=loader,
            supervisor_factory=supervisor,
        )
        result = await runner.run_challenge("crypto_basic_001")
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        call_count = 0

        async def flaky_supervisor():
            nonlocal call_count
            call_count += 1
            return make_fake_supervisor_result(solved=(call_count >= 3))

        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
        controller = RetryController(max_attempts=5)
        runner = BenchmarkRunner(
            challenge_loader=loader,
            supervisor_factory=flaky_supervisor,
            retry_controller=controller,
        )
        result = await runner.run_challenge("crypto_basic_001")
        assert result.status == "solved"
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_metrics_recorded(self):
        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
        supervisor = AsyncMock(return_value=make_fake_supervisor_result(solved=True))
        runner = BenchmarkRunner(
            challenge_loader=loader,
            supervisor_factory=supervisor,
        )
        await runner.run_challenge("crypto_basic_001")
        assert runner.metrics.total == 1

    @pytest.mark.asyncio
    async def test_run_dataset(self):
        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
        supervisor = AsyncMock(return_value=make_fake_supervisor_result(solved=True))
        runner = BenchmarkRunner(
            challenge_loader=loader,
            supervisor_factory=supervisor,
        )
        results = await runner.run_dataset(["crypto_basic_001", "malware_basic_001"])
        assert len(results) == 2
        assert all(r.status == "solved" for r in results)

    @pytest.mark.asyncio
    async def test_history_saved(self):
        with tempfile.TemporaryDirectory() as td:
            loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
            supervisor = AsyncMock(return_value=make_fake_supervisor_result(solved=True))
            history = BenchmarkHistory(storage_dir=td)
            runner = BenchmarkRunner(
                challenge_loader=loader,
                supervisor_factory=supervisor,
                history=history,
            )
            await runner.run_challenge("crypto_basic_001")
            saved = history.load_all()
            assert len(saved) >= 1


# ===================================================================
# FailureAnalyzer
# ===================================================================

class TestFailureAnalyzer:
    def test_solved_returns_none(self):
        fa = FailureAnalyzer()
        r = BenchmarkResult(challenge_id="x", category="c", difficulty="d", status="solved", flag_result="PASS")
        analysis = fa.analyze(r)
        assert analysis["category"] is None

    def test_classifies_missing_skill(self):
        fa = FailureAnalyzer()
        r = BenchmarkResult(challenge_id="x", category="crypto", difficulty="medium", status="failed",
                            failure_reason="missing skill: AES analysis not found")
        analysis = fa.analyze(r)
        assert analysis["category"] == "missing_skill"

    def test_classifies_wrong_agent(self):
        fa = FailureAnalyzer()
        r = BenchmarkResult(challenge_id="x", category="web", difficulty="medium", status="failed",
                            failure_reason="wrong agent: crypto_agent not suited for web challenge")
        analysis = fa.analyze(r)
        assert analysis["category"] == "wrong_agent"

    def test_classify_convenience_method(self):
        fa = FailureAnalyzer()
        r = BenchmarkResult(challenge_id="x", category="c", difficulty="d", status="failed",
                            failure_reason="tool not found")
        cat = fa.classify(r)
        assert cat == "missing_tool"

    def test_unknown_failure(self):
        fa = FailureAnalyzer()
        r = BenchmarkResult(challenge_id="x", category="c", difficulty="d", status="failed")
        analysis = fa.analyze(r)
        assert analysis["category"] is not None

    def test_recommendation_generated(self):
        fa = FailureAnalyzer()
        r = BenchmarkResult(challenge_id="x", category="crypto", difficulty="hard", status="failed",
                            failure_reason="missing skill")
        analysis = fa.analyze(r)
        assert "recommendation" in analysis
        assert len(analysis["recommendation"]) > 0


# ===================================================================
# RetryController
# ===================================================================

class TestRetryController:
    def test_default_max_attempts(self):
        rc = RetryController()
        assert rc.max_attempts == 3

    def test_custom_max_attempts(self):
        rc = RetryController(max_attempts=5)
        assert rc.max_attempts == 5

    def test_register_failure(self):
        rc = RetryController()
        rc.register_failure("crypto_001", {"category": "missing_skill", "recommendation": "add skill"})
        assert rc.total_failures == 1

    def test_exceeded(self):
        rc = RetryController(max_attempts=3)
        assert rc.exceeded("x", 3) is True
        assert rc.exceeded("x", 2) is False

    def test_get_strategy_initial(self):
        rc = RetryController()
        strategy = rc.get_strategy("crypto_001", 1)
        assert strategy["action"] == "initial_attempt"

    def test_get_strategy_after_failure(self):
        rc = RetryController()
        rc.register_failure("crypto_001", {"category": "missing_skill", "recommendation": "add skill"})
        strategy = rc.get_strategy("crypto_001", 2)
        assert strategy["action"] == "retry"
        assert strategy["category"] == "missing_skill"

    def test_clear(self):
        rc = RetryController()
        rc.register_failure("x", {"category": "missing_skill"})
        rc.clear("x")
        assert rc.total_failures == 0

    def test_clear_all(self):
        rc = RetryController()
        rc.register_failure("x", {"category": "a"})
        rc.register_failure("y", {"category": "b"})
        rc.clear_all()
        assert rc.total_failures == 0


# ===================================================================
# AgentMetricsTracker
# ===================================================================

class TestAgentMetricsTracker:
    def test_record_and_get(self):
        tracker = AgentMetricsTracker()
        tracker.record("crypto_agent", solved=True, confidence=0.85, category="crypto", tools_used=["python"])
        stats = tracker.get("crypto_agent")
        assert stats is not None
        assert stats.challenges_attempted == 1
        assert stats.solved == 1
        assert stats.success_rate == 1.0

    def test_multiple_agents(self):
        tracker = AgentMetricsTracker()
        tracker.record("crypto_agent", solved=True, confidence=0.9, category="crypto")
        tracker.record("malware_agent", solved=False, confidence=0.3, category="malware")
        tracker.record("crypto_agent", solved=False, confidence=0.5, category="crypto")
        assert tracker.get("crypto_agent").challenges_attempted == 2
        assert tracker.get("crypto_agent").solved == 1
        assert tracker.get("crypto_agent").success_rate == 0.5
        assert tracker.get("malware_agent").failed == 1

    def test_all(self):
        tracker = AgentMetricsTracker()
        tracker.record("crypto_agent", solved=True, confidence=0.9, category="crypto", tools_used=["python"])
        all_agents = tracker.all()
        assert "crypto_agent" in all_agents

    def test_weakest(self):
        tracker = AgentMetricsTracker()
        tracker.record("crypto_agent", solved=True)
        tracker.record("malware_agent", solved=False)
        weakest = tracker.get_weakest()
        assert weakest == "malware_agent"

    def test_strongest(self):
        tracker = AgentMetricsTracker()
        tracker.record("crypto_agent", solved=True)
        tracker.record("malware_agent", solved=False)
        strongest = tracker.get_strongest()
        assert strongest == "crypto_agent"

    def test_clear(self):
        tracker = AgentMetricsTracker()
        tracker.record("crypto_agent", solved=True)
        tracker.clear()
        assert tracker.total_agents == 0


# ===================================================================
# Evaluator
# ===================================================================

class TestEvaluator:
    def test_generate_report(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        evaluator = Evaluator(metrics=mc)
        report = evaluator.generate_report(dataset_name="test_run")
        assert report.dataset_name == "test_run"
        assert report.total_challenges == 4
        assert report.solved == 3
        assert report.success_rate == 0.75
        assert report.average_confidence > 0

    def test_report_by_category(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        evaluator = Evaluator(metrics=mc)
        report = evaluator.generate_report()
        assert "crypto" in report.by_category
        assert "malware" in report.by_category

    def test_report_weakest_area(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        evaluator = Evaluator(metrics=mc)
        report = evaluator.generate_report()
        assert "malware" in report.weakest_area.lower()

    def test_report_recommendations(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        evaluator = Evaluator(metrics=mc)
        report = evaluator.generate_report()
        assert len(report.recommendations) >= 1

    def test_report_to_json(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        evaluator = Evaluator(metrics=mc)
        report = evaluator.generate_report()
        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["total_challenges"] == 4

    def test_report_summary_table(self, sample_results):
        mc = MetricsCollector()
        mc.record_many(sample_results)
        evaluator = Evaluator(metrics=mc)
        report = evaluator.generate_report()
        table = report.summary_table()
        assert "CTF Benchmark Report" in table
        assert "75.0%" in table


# ===================================================================
# Memory Systems
# ===================================================================

class TestStrategyMemory:
    def test_record_and_get(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("crypto", "Try RSA small exponent analysis first", 0.85)
            mem.record("crypto", "Check for padding oracle", 0.7)
            strategies = mem.get_strategies("crypto")
            assert len(strategies) == 2
            assert strategies[0] == "Try RSA small exponent analysis first"

    def test_get_best(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("web", "Check for SSTI", 0.6)
            mem.record("web", "Check for SQL injection", 0.9)
            best = mem.get_best("web")
            assert best == "Check for SQL injection"

    def test_get_all(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("crypto", "strategy1", 0.5)
            all_s = mem.get_all()
            assert "crypto" in all_s

    def test_duplicate_updates_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("crypto", "strategy1", 0.5)
            mem.record("crypto", "strategy1", 0.9)
            strategies = mem.get_strategies("crypto")
            assert len(strategies) == 1
            assert mem.get_best("crypto") == "strategy1"

    def test_empty_category(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            assert mem.get_strategies("nonexistent") == []
            assert mem.get_best("nonexistent") is None


class TestFailureMemory:
    def test_record_and_get(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FailureMemory(storage_dir=td)
            mem.record("crypto_001", "crypto", "wrong key size", "missing_skill", "add RSA skill")
            failures = mem.get_failures()
            assert len(failures) == 1

    def test_get_by_category(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FailureMemory(storage_dir=td)
            mem.record("crypto_001", "crypto", "reason1", "missing_skill")
            mem.record("web_001", "web", "reason2", "wrong_agent")
            crypto = mem.get_failures("crypto")
            assert len(crypto) == 1
            assert crypto[0]["failure_type"] == "missing_skill"

    def test_get_common_failures(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FailureMemory(storage_dir=td)
            mem.record("a", "crypto", "r1", "missing_skill")
            mem.record("b", "crypto", "r2", "missing_skill")
            mem.record("c", "web", "r3", "wrong_agent")
            common = mem.get_common_failures(2)
            assert common[0][0] == "missing_skill"

    def test_get_recommendations(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FailureMemory(storage_dir=td)
            mem.record("a", "crypto", "r1", "missing_skill", "Add RSA skill")
            mem.record("b", "web", "r2", "wrong_agent", "Fix agent selection")
            recs = mem.get_recommendations()
            assert len(recs) == 2

    def test_clear(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FailureMemory(storage_dir=td)
            mem.record("a", "c", "r", "t")
            mem.clear()
            assert len(mem.get_failures()) == 0


class TestSolutionMemory:
    def test_record_and_get(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SolutionMemory(storage_dir=td)
            mem.record("crypto_001", "crypto", "medium", "small exponent attack",
                       ["python"], ["crypto_agent"], success=True)
            solutions = mem.get_solutions()
            assert len(solutions) == 1

    def test_get_by_category_and_success(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SolutionMemory(storage_dir=td)
            mem.record("crypto_001", "crypto", "medium", "approach1", ["python"], ["a"], True)
            mem.record("web_001", "web", "medium", "approach2", ["curl"], ["b"], False)
            crypto = mem.get_solutions(category="crypto", success=True)
            assert len(crypto) == 1
            assert crypto[0]["approach"] == "approach1"

    def test_get_successful_approaches(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SolutionMemory(storage_dir=td)
            mem.record("a", "crypto", "medium", "small exponent", ["python"], ["a"], True)
            mem.record("b", "crypto", "medium", "padding oracle", ["python"], ["a"], True)
            mem.record("c", "crypto", "hard", "bad approach", ["python"], ["a"], False)
            approaches = mem.get_successful_approaches("crypto")
            assert len(approaches) == 2
            assert "small exponent" in approaches

    def test_clear(self):
        with tempfile.TemporaryDirectory() as td:
            mem = SolutionMemory(storage_dir=td)
            mem.record("a", "c", "d", "approach", ["t"], ["a"], True)
            mem.clear()
            assert len(mem.get_solutions()) == 0


# ===================================================================
# DatasetLoader
# ===================================================================

class TestDatasetLoader:
    def test_list_datasets(self):
        loader = DatasetLoader()
        datasets = loader.list_datasets()
        assert "medium" in datasets

    def test_load_medium_dataset(self):
        loader = DatasetLoader()
        challenges = loader.load_dataset("medium")
        assert len(challenges) >= 20
        ids = [c["id"] for c in challenges]
        assert "crypto_medium_001" in ids
        assert "web_medium_001" in ids
        assert "malware_medium_001" in ids
        assert "forensics_medium_001" in ids

    def test_get_challenge_ids(self):
        loader = DatasetLoader()
        ids = loader.get_challenge_ids("medium")
        assert len(ids) == 20

    def test_get_categories(self):
        loader = DatasetLoader()
        cats = loader.get_categories("medium")
        assert len(cats) >= 4
        assert len(cats.get("crypto", [])) == 5
        assert len(cats.get("web", [])) == 5
        assert len(cats.get("malware", [])) == 5
        assert len(cats.get("forensics", [])) == 5

    def test_missing_dataset(self):
        loader = DatasetLoader()
        challenges = loader.load_dataset("nonexistent")
        assert challenges == []


# ===================================================================
# BenchmarkReport
# ===================================================================

class TestBenchmarkReport:
    def test_default_creation(self):
        report = BenchmarkReport(dataset_name="test")
        assert report.total_challenges == 0
        assert report.solved == 0
        assert report.success_rate == 0.0

    def test_to_dict(self):
        report = BenchmarkReport(dataset_name="test", total_challenges=10, solved=7, success_rate=0.7)
        d = report.to_dict()
        assert d["total_challenges"] == 10
        assert d["solved"] == 7

    def test_summary_table_format(self):
        report = BenchmarkReport(dataset_name="demo", total_challenges=5, solved=3, success_rate=0.6,
                                 by_category={"crypto": {"solved": 2, "total": 3, "success_rate": 0.667}})
        table = report.summary_table()
        assert "CTF Benchmark Report" in table
        assert "demo" in table

    def test_weakest_area_in_summary(self):
        report = BenchmarkReport(dataset_name="test", total_challenges=10, solved=3, success_rate=0.3,
                                 weakest_area="malware (0.0%)", recommendations=["Add malware skills"])
        table = report.summary_table()
        assert "Weakest Area" in table
        assert "Add malware skills" in table


# ===================================================================
# BenchmarkHistory
# ===================================================================

class TestBenchmarkHistory:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            history = BenchmarkHistory(storage_dir=td)
            r = BenchmarkResult(challenge_id="test_001", category="crypto", difficulty="medium", status="solved")
            path = history.save(r)
            assert Path(path).exists()
            loaded = history.load(Path(path).name)
            assert loaded is not None
            assert loaded.challenge_id == "test_001"

    def test_save_batch(self):
        with tempfile.TemporaryDirectory() as td:
            history = BenchmarkHistory(storage_dir=td)
            results = [
                BenchmarkResult(challenge_id="a", category="crypto", difficulty="medium", status="solved"),
                BenchmarkResult(challenge_id="b", category="web", difficulty="medium", status="failed"),
            ]
            paths = history.save_batch(results)
            assert len(paths) == 2

    def test_load_all(self):
        with tempfile.TemporaryDirectory() as td:
            history = BenchmarkHistory(storage_dir=td)
            history.save(BenchmarkResult(challenge_id="a", category="c", difficulty="d", status="solved"))
            history.save(BenchmarkResult(challenge_id="b", category="c", difficulty="d", status="failed"))
            all_r = history.load_all()
            assert len(all_r) == 2

    def test_list_sessions(self):
        with tempfile.TemporaryDirectory() as td:
            history = BenchmarkHistory(storage_dir=td)
            history.save(BenchmarkResult(challenge_id="a", category="c", difficulty="d", status="solved"))
            sessions = history.list_sessions()
            assert len(sessions) >= 1
            assert sessions[0]["filename"].endswith(".json")

    def test_get_statistics(self):
        with tempfile.TemporaryDirectory() as td:
            history = BenchmarkHistory(storage_dir=td)
            history.save(BenchmarkResult(challenge_id="a", category="c", difficulty="d", status="solved"))
            history.save(BenchmarkResult(challenge_id="b", category="c", difficulty="d", status="failed"))
            stats = history.get_statistics()
            assert stats["total"] == 2
            assert stats["solved"] == 1


# ===================================================================
# End-to-End Benchmark Workflow
# ===================================================================

class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_benchmark_workflow(self):
        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
        supervisor = AsyncMock(return_value=make_fake_supervisor_result(solved=True))

        with tempfile.TemporaryDirectory() as td:
            history = BenchmarkHistory(storage_dir=td)
            runner = BenchmarkRunner(
                challenge_loader=loader,
                supervisor_factory=supervisor,
                history=history,
            )
            results = await runner.run_dataset(["crypto_basic_001", "web_basic_001", "malware_basic_001"])
            assert len(results) == 3
            assert all(r.solved for r in results)

            evaluator = Evaluator(metrics=runner.metrics)
            report = evaluator.generate_report(dataset_name="e2e_test")
            assert report.total_challenges == 3
            assert report.solved == 3
            assert report.success_rate == 1.0

            table = report.summary_table()
            assert "100.0%" in table

    @pytest.mark.asyncio
    async def test_benchmark_with_failures_and_retries(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            return make_fake_supervisor_result(solved=(call_count >= 4))

        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))
        runner = BenchmarkRunner(
            challenge_loader=loader,
            supervisor_factory=flaky,
            retry_controller=RetryController(max_attempts=5),
        )
        result = await runner.run_challenge("crypto_basic_001")
        assert result.status == "solved"
        assert result.attempts >= 2

    @pytest.mark.asyncio
    async def test_agent_tracking_integration(self):
        tracker = AgentMetricsTracker()
        loader = ChallengeLoader(challenges_dir=str(Path.cwd() / "challenges"))

        async def solving_supervisor():
            return make_fake_supervisor_result(solved=True)

        runner = BenchmarkRunner(
            challenge_loader=loader,
            supervisor_factory=solving_supervisor,
        )
        result = await runner.run_challenge("crypto_basic_001")
        for agent_name in result.agents_used:
            tracker.record(agent_name, solved=result.solved, confidence=result.confidence,
                          category=result.category, tools_used=result.tools_used)
        assert tracker.total_agents >= 1
