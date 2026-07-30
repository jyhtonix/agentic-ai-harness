"""Tests for the Real CTF Validation & Optimization Framework.

Covers:
  - CTFSourceRegistry
  - ModelRegistry / ModelConfig
  - ModelBenchmarkRunner
  - ComparisonEngine
  - HardModeController
  - AgentDebate
  - Enhanced StrategyMemory (failed approaches)
  - OptimizationReport / OptimizationEngine
  - External dataset loading
  - SupervisorAgent backward compatibility
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest
import yaml

from benchmark_engine.source_registry import CTFSourceRegistry
from benchmark_engine.model_runner import ModelBenchmarkRunner, ModelBenchmarkResult
from benchmark_engine.comparison import ComparisonEngine, ComparisonReport, ModelComparisonEntry
from benchmark_engine.hard_mode import HardModeController
from benchmark_engine.optimization import OptimizationEngine, OptimizationReport, CapabilitySummary
from benchmark_engine.results import BenchmarkResult
from benchmark_engine.metrics import MetricsCollector

from models import ModelConfig, ModelRegistry
from agents.team.debate import AgentDebate, DebateArgument, ConsensusFinding
from agents.team.evidence import AgentFinding
from memory.strategies import StrategyMemory

from benchmark_engine.dataset import DatasetLoader


# ===================================================================
# CTFSourceRegistry
# ===================================================================

class TestCTFSourceRegistry:
    def test_builtin_sources(self):
        reg = CTFSourceRegistry()
        assert "educational_ctf" in reg
        assert "picoctf" in reg
        assert len(reg) >= 6

    def test_get_source(self):
        reg = CTFSourceRegistry()
        src = reg.get("educational_ctf")
        assert src is not None
        assert src["type"] == "educational"

    def test_get_missing(self):
        reg = CTFSourceRegistry()
        assert reg.get("nonexistent") is None

    def test_list_sources(self):
        reg = CTFSourceRegistry()
        sources = reg.list_sources()
        assert len(sources) >= 6

    def test_get_by_type(self):
        reg = CTFSourceRegistry()
        educational = reg.get_by_type("educational")
        assert len(educational) >= 1
        for s in educational.values():
            assert s["type"] == "educational"

    def test_register_custom(self):
        reg = CTFSourceRegistry()
        reg.register("custom_ctf", {"name": "Custom", "type": "private", "license": "proprietary"})
        assert "custom_ctf" in reg
        assert reg.get("custom_ctf")["name"] == "Custom"

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "sources.yaml"
            with open(f, "w") as fh:
                yaml.dump({"sources": {"test_src": {"name": "Test", "type": "test"}}}, fh)
            reg = CTFSourceRegistry(sources_file=str(f))
            assert "test_src" in reg


# ===================================================================
# ModelConfig / ModelRegistry
# ===================================================================

class TestModelConfig:
    def test_creation(self):
        mc = ModelConfig(name="Test Model", provider="Test", model_id="test-model", temperature=0.5)
        assert mc.name == "Test Model"
        assert mc.model_id == "test-model"

    def test_to_dict(self):
        mc = ModelConfig(name="M", provider="P", model_id="m1", available_tools=["python"])
        d = mc.to_dict()
        assert d["name"] == "M"
        assert d["available_tools"] == ["python"]

    def test_from_dict(self):
        mc = ModelConfig.from_dict({"name": "Test", "provider": "P", "model_id": "t1", "temperature": 0.7})
        assert mc.name == "Test"
        assert mc.temperature == 0.7


class TestModelRegistry:
    def test_discover_builtin_models(self):
        reg = ModelRegistry()
        assert len(reg) >= 4
        assert "deepseek-v4-flash-free" in reg

    def test_get_by_id(self):
        reg = ModelRegistry()
        mc = reg.get("deepseek-v4-flash-free")
        assert mc is not None
        assert "DeepSeek" in mc.name

    def test_get_by_name(self):
        reg = ModelRegistry()
        mc = reg.get_by_name("Claude 4 Sonnet")
        assert mc is not None
        assert mc.provider == "Anthropic"

    def test_list_models(self):
        reg = ModelRegistry()
        models = reg.list_models()
        assert len(models) >= 4

    def test_register(self):
        reg = ModelRegistry()
        mc = ModelConfig(name="Custom", provider="Me", model_id="custom-v1")
        reg.register(mc)
        assert "custom-v1" in reg
        assert reg.get_by_name("Custom") is not None


# ===================================================================
# ModelBenchmarkRunner
# ===================================================================

class TestModelBenchmarkRunner:
    @pytest.mark.asyncio
    async def test_run_model_no_factory(self):
        runner = ModelBenchmarkRunner()
        results = await runner.run_model("deepseek-v4-flash-free", ["crypto_001"])
        assert len(results) == 1
        assert results[0].model_name == "DeepSeek V4 Flash Free"

    @pytest.mark.asyncio
    async def test_run_unknown_model(self):
        runner = ModelBenchmarkRunner()
        results = await runner.run_model("nonexistent", ["crypto_001"])
        assert results == []

    @pytest.mark.asyncio
    async def test_model_benchmark_result(self):
        r = ModelBenchmarkResult(
            model_name="Test", model_id="test-v1",
            challenge_id="c_001", category="crypto", difficulty="medium",
            status="solved",
        )
        d = r.to_dict()
        assert d["model_name"] == "Test"
        assert d["model_id"] == "test-v1"

    @pytest.mark.asyncio
    async def test_run_models_multiple(self):
        runner = ModelBenchmarkRunner()
        results = await runner.run_models(
            ["deepseek-v4-flash-free", "nonexistent"],
            ["crypto_001"]
        )
        assert "deepseek-v4-flash-free" in results
        assert "nonexistent" in results

    @pytest.mark.asyncio
    async def test_get_model_metrics(self):
        runner = ModelBenchmarkRunner()
        await runner.run_model("deepseek-v4-flash-free", ["crypto_001"])
        mc = runner.get_model_metrics("deepseek-v4-flash-free")
        assert mc.total >= 1


# ===================================================================
# ComparisonEngine
# ===================================================================

class TestComparisonEngine:
    def test_add_results(self):
        engine = ComparisonEngine()
        engine.add_model_results("model_a", [
            ModelBenchmarkResult(model_name="A", model_id="a", challenge_id="c1",
                                 category="crypto", difficulty="medium", status="solved"),
        ])
        engine.add_model_results("model_b", [
            ModelBenchmarkResult(model_name="B", model_id="b", challenge_id="c1",
                                 category="crypto", difficulty="medium", status="failed"),
        ])
        report = engine.compare(dataset_name="test")
        assert len(report.models) == 2
        assert report.best_model == "model_a"

    def test_compare_ranking(self):
        engine = ComparisonEngine()
        mc1 = MetricsCollector()
        mc1.record(BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="solved"))
        mc1.record(BenchmarkResult(challenge_id="c2", category="c", difficulty="m", status="failed"))
        mc2 = MetricsCollector()
        mc2.record(BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="solved"))
        mc2.record(BenchmarkResult(challenge_id="c2", category="c", difficulty="m", status="solved"))

        engine.add_model_metrics("model_a", mc1)
        engine.add_model_metrics("model_b", mc2)
        report = engine.compare()
        assert report.models[0].model_id == "model_b"
        assert report.models[0].success_rate > report.models[1].success_rate

    def test_empty_compare(self):
        engine = ComparisonEngine()
        report = engine.compare()
        assert len(report.models) == 0
        assert report.best_model == ""

    def test_summary_table(self):
        engine = ComparisonEngine()
        engine.add_model_results("model_a", [
            ModelBenchmarkResult(model_name="A", model_id="a", challenge_id="c1",
                                 category="c", difficulty="m", status="solved"),
        ])
        report = engine.compare("dataset")
        table = report.summary_table()
        assert "Model Comparison Report" in table
        assert "A" in table

    def test_to_dict(self):
        engine = ComparisonEngine()
        engine.add_model_results("model_a", [
            ModelBenchmarkResult(model_name="A", model_id="a", challenge_id="c1",
                                 category="c", difficulty="m", status="solved",
                                 execution_time=1.5),
        ])
        report = engine.compare("test")
        d = report.to_dict()
        assert d["dataset_name"] == "test"
        assert len(d["models"]) == 1


# ===================================================================
# HardModeController
# ===================================================================

class TestHardModeController:
    def test_default_strategy(self):
        ctrl = HardModeController()
        strategy = ctrl.get_strategy("challenge_1")
        assert strategy["strategy"] == "default"
        assert strategy["attempt"] == 1

    def test_strategy_rotation(self):
        ctrl = HardModeController(max_attempts=6)
        result = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="hard",
                                 status="failed", flag_result="FAIL")
        for _ in range(3):
            ctrl.register_outcome("c1", result)

        strategy = ctrl.get_strategy("c1")
        assert strategy["attempt"] == 4

    def test_register_outcome_solved(self):
        ctrl = HardModeController()
        solved = BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="solved", flag_result="PASS")
        outcome = ctrl.register_outcome("c1", solved)
        assert outcome["status"] == "solved"

    def test_register_outcome_failed(self):
        ctrl = HardModeController()
        failed = BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="failed")
        outcome = ctrl.register_outcome("c1", failed)
        assert outcome["status"] == "failed"
        assert "next_strategy" in outcome

    def test_should_retry(self):
        ctrl = HardModeController(max_attempts=3)
        assert ctrl.should_retry("c1") is True
        failed = BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="failed")
        ctrl.register_outcome("c1", failed)
        ctrl.register_outcome("c1", failed)
        ctrl.register_outcome("c1", failed)
        assert ctrl.should_retry("c1") is False

    def test_reset(self):
        ctrl = HardModeController()
        failed = BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="failed")
        ctrl.register_outcome("c1", failed)
        assert ctrl.total_active == 1
        ctrl.reset("c1")
        assert ctrl.total_active == 0

    def test_reset_all(self):
        ctrl = HardModeController()
        failed = BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="failed")
        ctrl.register_outcome("c1", failed)
        ctrl.register_outcome("c2", failed)
        assert ctrl.total_active == 2
        ctrl.reset_all()
        assert ctrl.total_active == 0


# ===================================================================
# AgentDebate
# ===================================================================

class TestAgentDebate:
    def test_submit_argument(self):
        debate = AgentDebate()
        arg = DebateArgument(agent_name="crypto_agent", position="RSA small exponent",
                             evidence=["key.pub"], confidence=0.85)
        debate.submit_argument("challenge_1", arg)
        args = debate.get_arguments("challenge_1")
        assert len(args) == 1

    def test_submit_finding(self):
        debate = AgentDebate()
        finding = AgentFinding(agent_name="crypto_agent", findings=["RSA attack found"],
                               evidence=["key.pub"], confidence=0.9)
        debate.submit_finding("challenge_1", finding)
        args = debate.get_arguments("challenge_1")
        assert len(args) == 1
        assert args[0].position == "RSA attack found"

    def test_resolve_consensus(self):
        debate = AgentDebate()
        debate.submit_argument("topic", DebateArgument("a1", "RSA weak key", ["k"], 0.9))
        debate.submit_argument("topic", DebateArgument("a2", "RSA weak key confirmed", ["k2"], 0.8))
        finding = debate.resolve("topic")
        assert finding is not None
        assert "RSA" in finding.consensus

    def test_resolve_dissenting(self):
        debate = AgentDebate()
        debate.submit_argument("topic", DebateArgument("a1", "RSA weak key", ["k"], 0.9))
        debate.submit_argument("topic", DebateArgument("a2", "AES encryption", ["k2"], 0.7))
        finding = debate.resolve("topic")
        assert finding is not None
        assert len(finding.dissenting_opinions) >= 1

    def test_resolve_no_arguments(self):
        debate = AgentDebate()
        finding = debate.resolve("nonexistent")
        assert finding is None

    def test_clear(self):
        debate = AgentDebate()
        debate.submit_argument("t", DebateArgument("a", "pos", ["e"], 0.8))
        debate.clear("t")
        assert debate.get_arguments("t") == []

    def test_clear_all(self):
        debate = AgentDebate()
        debate.submit_argument("t1", DebateArgument("a", "p1", ["e"], 0.8))
        debate.submit_argument("t2", DebateArgument("a", "p2", ["e"], 0.9))
        debate.clear_all()
        assert debate.get_arguments("t1") == []
        assert debate.get_arguments("t2") == []


# ===================================================================
# StrategyMemory (Enhanced with failed approaches)
# ===================================================================

class TestEnhancedStrategyMemory:
    def test_record_failed_approach(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record_failed("crypto", "Start with brute force", "Too many possibilities")
            failed = mem.get_failed_approaches("crypto")
            assert len(failed) == 1
            assert "brute force" in failed[0]

    def test_failed_approach_tracking(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record_failed("crypto", "Bad approach")
            mem.record_failed("crypto", "Bad approach")
            entries = mem.get_all_failed()
            crypto_entries = entries.get("crypto", [])
            assert crypto_entries[0].get("failure_count", 0) >= 2

    def test_category_patterns(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("crypto", "Good approach", 0.9)
            mem.record_failed("crypto", "Bad approach", "Wrong")
            patterns = mem.get_category_patterns("crypto")
            assert "successful_approaches" in patterns
            assert "failed_approaches" in patterns
            assert "avoid_strategies" in patterns
            assert "AVOID" in patterns["avoid_strategies"][0]

    def test_empty_category_patterns(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            patterns = mem.get_category_patterns("nonexistent")
            assert patterns["successful_approaches"] == []
            assert patterns["failed_approaches"] == []


# ===================================================================
# OptimizationReport / OptimizationEngine
# ===================================================================

class TestOptimizationReport:
    def test_report_creation(self):
        report = OptimizationReport(
            dataset_name="test",
            total_challenges=10,
            overall_success_rate=0.7,
        )
        assert report.dataset_name == "test"
        assert report.total_challenges == 10

    def test_to_dict(self):
        report = OptimizationReport(dataset_name="test", total_challenges=5, overall_success_rate=0.6)
        report.capabilities.append(CapabilitySummary(
            category="crypto", success_rate=0.8, solved=4, total=5,
            average_confidence=0.85, common_failures=["missing_skill"],
        ))
        d = report.to_dict()
        assert d["total_challenges"] == 5
        assert len(d["capabilities"]) == 1

    def test_summary_table(self):
        report = OptimizationReport(dataset_name="bench", total_challenges=20, overall_success_rate=0.65)
        report.capabilities.append(CapabilitySummary("crypto", 0.8, 4, 5, 0.85))
        report.capabilities.append(CapabilitySummary("malware", 0.4, 2, 5, 0.5))
        report.weakest_category = "malware (40%)"
        table = report.summary_table()
        assert "Optimization Report" in table
        assert "Success Rate: 65.0%" in table or "65.0" in table
        assert "malware" in table

    def test_to_json(self):
        report = OptimizationReport(dataset_name="t", total_challenges=3, overall_success_rate=1.0)
        j = report.to_json()
        d = json.loads(j)
        assert d["overall_success_rate"] == 1.0


class TestOptimizationEngine:
    def test_generate_report(self):
        mc = MetricsCollector()
        mc.record(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="medium", status="solved", flag_result="PASS", confidence=0.9))
        mc.record(BenchmarkResult(challenge_id="c2", category="crypto", difficulty="medium", status="solved", flag_result="PASS", confidence=0.8))
        mc.record(BenchmarkResult(challenge_id="c3", category="malware", difficulty="hard", status="failed", flag_result="FAIL", confidence=0.3, failure_reason="missing skill"))
        mc.record(BenchmarkResult(challenge_id="c4", category="malware", difficulty="hard", status="failed", flag_result="FAIL", confidence=0.2, failure_reason="insufficient reasoning"))

        engine = OptimizationEngine(metrics=mc)
        report = engine.generate(dataset_name="validation")
        assert report.dataset_name == "validation"
        assert report.total_challenges == 4
        assert report.overall_success_rate == 0.5
        assert len(report.capabilities) >= 2

    def test_weakest_and_strongest(self):
        mc = MetricsCollector()
        mc.record(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m", status="solved", flag_result="PASS"))
        mc.record(BenchmarkResult(challenge_id="c2", category="malware", difficulty="h", status="failed", flag_result="FAIL"))

        engine = OptimizationEngine(metrics=mc)
        report = engine.generate()
        assert "crypto" in report.strongest_category
        assert "malware" in report.weakest_category

    def test_improvement_actions(self):
        mc = MetricsCollector()
        for i in range(3):
            mc.record(BenchmarkResult(challenge_id=f"w{i}", category="web", difficulty="m", status="failed", flag_result="FAIL", failure_reason="missing tool"))
        for i in range(3):
            mc.record(BenchmarkResult(challenge_id=f"c{i}", category="crypto", difficulty="m", status="solved", flag_result="PASS"))

        engine = OptimizationEngine(metrics=mc)
        report = engine.generate()
        web_actions = [a for a in report.improvement_actions if "web" in a.lower()]
        assert len(web_actions) >= 1

    def test_with_model_comparison(self):
        mc = MetricsCollector()
        mc.record(BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="solved"))
        comp = ComparisonReport(dataset_name="model_compare", models=[
            ModelComparisonEntry(model_name="A", model_id="a", solved=1, challenges_attempted=1, success_rate=1.0),
        ], best_model="A", best_rate=1.0)
        engine = OptimizationEngine(metrics=mc)
        report = engine.generate(model_comparison=comp)
        assert report.model_comparison is not None
        assert report.model_comparison.best_model == "A"


# ===================================================================
# External Dataset Loading
# ===================================================================

class TestExternalDatasets:
    def test_external_medium_exists(self):
        ds = DatasetLoader(datasets_dir=str(Path.cwd() / "benchmark" / "datasets" / "external"))
        datasets = ds.list_datasets()
        assert "medium" in datasets
        assert "hard" in datasets

    def test_external_medium_has_10_challenges(self):
        ds = DatasetLoader(datasets_dir=str(Path.cwd() / "benchmark" / "datasets" / "external"))
        challenges = ds.load_dataset("medium")
        assert len(challenges) == 10

    def test_external_hard_has_20_challenges(self):
        ds = DatasetLoader(datasets_dir=str(Path.cwd() / "benchmark" / "datasets" / "external"))
        challenges = ds.load_dataset("hard")
        assert len(challenges) == 20

    def test_total_external_30_challenges(self):
        ds = DatasetLoader(datasets_dir=str(Path.cwd() / "benchmark" / "datasets" / "external"))
        medium = ds.load_dataset("medium")
        hard = ds.load_dataset("hard")
        assert len(medium) + len(hard) == 30

    def test_categories_represented(self):
        ds = DatasetLoader(datasets_dir=str(Path.cwd() / "benchmark" / "datasets" / "external"))
        hard = ds.load_dataset("hard")
        cats = {c["category"] for c in hard}
        assert "crypto" in cats
        assert "web" in cats
        assert "malware" in cats
        assert "forensics" in cats


# ===================================================================
# Backward Compatibility
# ===================================================================

class TestBackwardCompatibility:
    def test_existing_imports_unaffected(self):
        """Core benchmark imports should still work."""
        from benchmark_engine import (
            BenchmarkRunner, MetricsCollector, BenchmarkResult, BenchmarkReport,
            Evaluator, FailureAnalyzer, AgentMetricsTracker, RetryController,
            BenchmarkHistory, DatasetLoader,
        )
        assert BenchmarkRunner is not None

    def test_strategy_memory_backward_compat(self):
        """Existing StrategyMemory API should be unchanged."""
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("crypto", "test strategy", 0.8)
            assert mem.get_best("crypto") == "test strategy"
            assert len(mem.get_strategies("crypto")) == 1
