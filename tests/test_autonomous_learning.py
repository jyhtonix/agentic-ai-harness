"""Tests for Autonomous CTF Reasoning & Self-Improvement Framework.

Covers:
  - ChallengeAnalyzerAgent
  - StrategyEvolutionEngine
  - SkillGapDetector
  - SkillImprovementProposal
  - StrategyRanker
  - Enhanced RetryController
  - AutonomousLearner
  - FeedbackCollector
  - KnowledgeUpdater
  - Competition mode (runner, scorer, leaderboard)
  - ImprovementReportGenerator
  - Backward compatibility
"""

import contextlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from agents.team.challenge_analyzer import ChallengeAnalyzerAgent
from benchmark_engine.strategy_evolution import StrategyEvolutionEngine
from benchmark_engine.skill_gap import SkillGapDetector
from benchmark_engine.results import BenchmarkResult
from benchmark_engine.metrics import MetricsCollector
from skills_engine.improvement import SkillImprovementProposal
from memory.strategy_ranker import StrategyRanker
from memory.strategies import StrategyMemory
from memory.failures import FailureMemory
from memory.solutions import SolutionMemory
from benchmark_engine.retry import RetryController
from learning_engine import AutonomousLearner, FeedbackCollector, KnowledgeUpdater
from competition import CompetitionRunner, Scorer, ScoreEntry, Leaderboard
from benchmark_engine.improvement_report import ImprovementReportGenerator


@contextlib.contextmanager
def _isolated_strategy_memory():
    """Yield a StrategyMemory backed by a temporary directory."""
    with tempfile.TemporaryDirectory() as td:
        yield StrategyMemory(storage_dir=td)


@contextlib.contextmanager
def _isolated_evolution_engine():
    """Yield a StrategyEvolutionEngine backed by a temporary store."""
    with tempfile.TemporaryDirectory() as td:
        yield StrategyEvolutionEngine(strategy_memory=StrategyMemory(storage_dir=td))


@contextlib.contextmanager
def _isolated_learner():
    """Yield an AutonomousLearner whose stores all live in a temp dir."""
    with tempfile.TemporaryDirectory() as td:
        strategy_memory = StrategyMemory(storage_dir=td)
        learner = AutonomousLearner(
            strategy_memory=strategy_memory,
            failure_memory=FailureMemory(storage_dir=td),
            solution_memory=SolutionMemory(storage_dir=td),
            strategy_evolution=StrategyEvolutionEngine(strategy_memory=strategy_memory),
        )
        yield learner


@contextlib.contextmanager
def _isolated_updater():
    """Yield a KnowledgeUpdater whose stores all live in a temp dir."""
    with tempfile.TemporaryDirectory() as td:
        updater = KnowledgeUpdater(
            strategy_memory=StrategyMemory(storage_dir=td),
            failure_memory=FailureMemory(storage_dir=td),
            solution_memory=SolutionMemory(storage_dir=td),
        )
        yield updater


@contextlib.contextmanager
def _isolated_report_generator():
    """Yield an ImprovementReportGenerator whose ranker writes to a temp dir."""
    with tempfile.TemporaryDirectory() as td:
        strategy_memory = StrategyMemory(storage_dir=td)
        ranker = StrategyRanker(strategy_memory=strategy_memory, storage_dir=td)
        yield ImprovementReportGenerator(strategy_ranker=ranker)


# ===================================================================
# ChallengeAnalyzerAgent
# ===================================================================

class TestChallengeAnalyzerAgent:
    def test_analyze_crypto(self):
        result = ChallengeAnalyzerAgent.analyze("Decrypt the RSA ciphertext and recover the flag")
        assert "crypto" in result["category"]
        assert result["complexity"] in ("low", "medium")

    def test_analyze_multi_domain(self):
        result = ChallengeAnalyzerAgent.analyze("Analyze the malware and decrypt the encoded strings")
        assert len(result["category"]) >= 2
        assert result["is_multi_stage"] is True

    def test_analyze_web(self):
        result = ChallengeAnalyzerAgent.analyze("Exploit SQL injection on the login page")
        assert "web" in result["category"]
        assert "curl" in result["recommended_tools"]

    def test_analyze_general_fallback(self):
        result = ChallengeAnalyzerAgent.analyze("Do something with this file")
        assert "general" in result["category"]

    def test_recommends_agents(self):
        result = ChallengeAnalyzerAgent.analyze("Crypto challenge with RSA")
        assert "CryptoAgent" in result["required_agents"]

    def test_high_complexity(self):
        result = ChallengeAnalyzerAgent.analyze("Complex multi-stage obfuscated malware analysis")
        assert result["complexity"] == "high"

    def test_recommended_strategy(self):
        result = ChallengeAnalyzerAgent.analyze("Web SQL injection detection")
        assert "web" in result["recommended_strategy"].lower()

    def test_required_skills_passthrough(self):
        result = ChallengeAnalyzerAgent.analyze("Test", required_skills=["crypto-basics"])
        assert "crypto-basics" in result["required_skills"]

    def test_analyze_forensics(self):
        result = ChallengeAnalyzerAgent.analyze("Extract metadata and find hidden artifacts in image")
        assert "forensics" in result["category"]

    def test_recommended_tools_deduped(self):
        result = ChallengeAnalyzerAgent.analyze("Analyze malware with encrypted payload")
        tools = result["recommended_tools"]
        assert len(tools) == len(set(tools))


# ===================================================================
# StrategyEvolutionEngine
# ===================================================================

class TestStrategyEvolutionEngine:
    def test_evolve_empty_results(self):
        with _isolated_evolution_engine() as engine:
            evolved = engine.evolve("crypto", [])
            assert len(evolved) >= 1

    def test_evolve_from_successes(self):
        with _isolated_evolution_engine() as engine:
            results = [
                BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m",
                               status="solved", flag_result="PASS", confidence=0.9,
                               tools_used=["python"], agents_used=["crypto_agent"]),
                BenchmarkResult(challenge_id="c2", category="crypto", difficulty="m",
                               status="solved", flag_result="PASS", confidence=0.8,
                               tools_used=["python"], agents_used=["crypto_agent"]),
            ]
            evolved = engine.evolve("crypto", results)
            assert len(evolved) >= 1
            assert any("python" in s for s in evolved)

    def test_evolve_from_failures(self):
        with _isolated_evolution_engine() as engine:
            results = [
                BenchmarkResult(challenge_id="c1", category="malware", difficulty="h",
                               status="failed", flag_result="FAIL", confidence=0.2,
                               failure_reason="missing PE analysis skill",
                               failure_category="missing_skill"),
            ]
            evolved = engine.evolve("malware", results)
            assert any("Avoid" in s or "Address" in s for s in evolved)

    def test_evolve_strategy_text(self):
        with _isolated_evolution_engine() as engine:
            text = engine.evolve_strategy_text("crypto", [])
            assert "Crypto Analysis Strategy:" in text

    def test_mixed_results(self):
        with _isolated_evolution_engine() as engine:
            results = [
                BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m",
                               status="solved", flag_result="PASS", confidence=0.9,
                               tools_used=["python"], agents_used=["crypto_agent"]),
                BenchmarkResult(challenge_id="c2", category="crypto", difficulty="m",
                               status="failed", flag_result="FAIL", confidence=0.2,
                               failure_reason="insufficient reasoning",
                               failure_category="insufficient_reasoning"),
            ]
            evolved = engine.evolve("crypto", results)
            assert len(evolved) >= 1


# ===================================================================
# SkillGapDetector
# ===================================================================

class TestSkillGapDetector:
    def test_solved_returns_no_gaps(self):
        detector = SkillGapDetector()
        r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m",
                           status="solved", flag_result="PASS")
        result = detector.analyze(r)
        assert result["gaps"] == []

    def test_non_skill_failure_returns_empty(self):
        detector = SkillGapDetector()
        r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m",
                           status="failed", failure_reason="timeout",
                           failure_category="timeout")
        result = detector.analyze(r)
        assert result["gaps"] == []

    def test_detects_pe_gap(self):
        detector = SkillGapDetector()
        r = BenchmarkResult(challenge_id="m1", category="malware", difficulty="h",
                           status="failed", failure_reason="missing pe analysis skill",
                           failure_category="missing_skill")
        result = detector.analyze(r)
        assert len(result["gaps"]) >= 1
        assert "pe" in " ".join(result["gaps"]).lower()

    def test_detects_rsa_gap(self):
        detector = SkillGapDetector()
        r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="h",
                           status="failed", failure_reason="no rsa analysis skill found",
                           failure_category="missing_skill")
        result = detector.analyze(r)
        assert len(result["gaps"]) >= 1

    def test_get_summary(self):
        detector = SkillGapDetector()
        r = BenchmarkResult(challenge_id="m1", category="malware", difficulty="h",
                           status="failed", failure_reason="missing pe analysis",
                           failure_category="missing_skill")
        detector.analyze(r)
        summary = detector.get_summary()
        assert "malware" in summary

    def test_get_top_gaps(self):
        detector = SkillGapDetector()
        for i in range(3):
            r = BenchmarkResult(challenge_id=f"m{i}", category="malware", difficulty="h",
                               status="failed", failure_reason="missing pe analysis skill",
                               failure_category="missing_skill")
            detector.analyze(r)
        top = detector.get_top_gaps(2)
        assert len(top) >= 1

    def test_confidence_increases_with_gaps(self):
        detector = SkillGapDetector()
        r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="h",
                           status="failed",
                           failure_reason="missing rsa and aes analysis skills",
                           failure_category="missing_skill")
        result = detector.analyze(r)
        assert result["confidence"] >= 0.5


# ===================================================================
# SkillImprovementProposal
# ===================================================================

class TestSkillImprovementProposal:
    def test_generate_proposal(self):
        proposer = SkillImprovementProposal()
        proposal = proposer.generate("pe-analysis", "malware", 0.85)
        assert proposal["proposed_skill_name"] == "pe-analysis"
        assert proposal["urgency"] == "high"

    def test_generate_unknown_gap(self):
        proposer = SkillImprovementProposal()
        proposal = proposer.generate("custom-skill-need", "general", 0.6)
        assert proposal["confidence"] == 0.6
        assert "custom-skill-need" in proposal["proposed_skill_name"]

    def test_generate_batch(self):
        proposer = SkillImprovementProposal()
        gaps = [{"gap": "pe-analysis", "category": "malware", "occurrences": 3},
                {"gap": "rsa-fundamentals", "category": "crypto", "occurrences": 2}]
        proposals = proposer.generate_batch(gaps)
        assert len(proposals) == 2

    def test_get_all_proposals(self):
        proposer = SkillImprovementProposal()
        proposer.generate("pe-analysis", "malware", 0.8)
        proposer.generate("web-security", "web", 0.7)
        all_p = proposer.get_all_proposals()
        assert len(all_p) == 2

    def test_format_report(self):
        proposer = SkillImprovementProposal()
        proposer.generate("pe-analysis", "malware", 0.85)
        report = proposer.format_report()
        assert "Skill Improvement Proposals" in report
        assert "PE Analysis" in report

    def test_clear(self):
        proposer = SkillImprovementProposal()
        proposer.generate("test", "general", 0.5)
        proposer.clear()
        assert proposer.get_all_proposals() == []


# ===================================================================
# StrategyRanker
# ===================================================================

class TestStrategyRanker:
    def test_rank_empty(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            ranker = StrategyRanker(strategy_memory=mem, storage_dir=td)
            ranked = ranker.rank("crypto")
            assert ranked == []

    def test_rank_with_strategies(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("crypto", "Check RSA parameters", 0.85)
            mem.record("crypto", "Brute force", 0.1)
            ranker = StrategyRanker(strategy_memory=mem, storage_dir=td)
            ranked = ranker.rank("crypto")
            assert len(ranked) >= 2
            assert ranked[0]["score"] >= ranked[1]["score"]

    def test_get_best(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("web", "SQL injection check first", 0.9)
            mem.record("web", "XSS check", 0.6)
            ranker = StrategyRanker(strategy_memory=mem, storage_dir=td)
            best = ranker.get_best("web")
            assert "SQL" in best

    def test_get_top_n(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("crypto", "s1", 0.9)
            mem.record("crypto", "s2", 0.7)
            mem.record("crypto", "s3", 0.5)
            ranker = StrategyRanker(strategy_memory=mem, storage_dir=td)
            top = ranker.get_top_n("crypto", 2)
            assert len(top) == 2

    def test_record_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            ranker = StrategyRanker(storage_dir=td)
            ranker.record_outcome("crypto", "test_strategy", True)
            rate = ranker.get_success_rate("crypto", "test_strategy")
            assert rate == 1.0

    def test_get_ranked_report(self):
        with tempfile.TemporaryDirectory() as td:
            mem = StrategyMemory(storage_dir=td)
            mem.record("crypto", "Check small exponent", 0.85)
            ranker = StrategyRanker(strategy_memory=mem, storage_dir=td)
            report = ranker.get_ranked_report("crypto")
            assert "Strategy Rankings" in report


# ===================================================================
# Enhanced RetryController
# ===================================================================

class TestEnhancedRetryController:
    def test_enhanced_phase_progression(self):
        ctrl = RetryController(max_attempts=6, use_enhanced=True)
        analysis = {"category": "missing_skill", "recommendation": "add skill"}
        for i in range(4):
            ctrl.register_failure("c1", analysis)

        strategy = ctrl.get_strategy("c1", 3)
        assert "phase" in strategy
        assert strategy["action"] == "retry"

    def test_enhanced_phases_cycle(self):
        ctrl = RetryController(max_attempts=7, use_enhanced=True)
        analysis = {"category": "missing_skill", "recommendation": "add skill"}
        phases_seen = set()
        for attempt in range(1, 7):
            ctrl.register_failure("c1", analysis)
            strategy = ctrl.get_strategy("c1", attempt)
            phases_seen.add(strategy.get("phase", ""))

        assert len(phases_seen) >= 4

    def test_standard_mode_unaffected(self):
        ctrl = RetryController(max_attempts=3, use_enhanced=False)
        analysis = {"category": "missing_skill", "recommendation": "add skill"}
        ctrl.register_failure("c1", analysis)
        strategy = ctrl.get_strategy("c1", 2)
        assert "phase" not in strategy


# ===================================================================
# AutonomousLearner
# ===================================================================

class TestAutonomousLearner:
    def test_learn_from_solved(self):
        with _isolated_learner() as learner:
            r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m",
                               status="solved", flag_result="PASS", confidence=0.9,
                               tools_used=["python"], agents_used=["crypto_agent"])
            entry = learner.learn_from_result(r)
            assert entry["status"] == "solved"
            assert "recorded_solution" in entry.get("actions_taken", [])

    def test_learn_from_failed(self):
        with _isolated_learner() as learner:
            r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="h",
                               status="failed", flag_result="FAIL",
                               failure_reason="missing skill for RSA",
                               failure_category="missing_skill")
            entry = learner.learn_from_result(r)
            assert entry["status"] == "failed"
            assert "detected_skill_gaps" in entry.get("actions_taken", [])

    def test_learn_from_results_batch(self):
        with _isolated_learner() as learner:
            results = [
                BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m",
                               status="solved", flag_result="PASS",
                               agents_used=["crypto_agent"]),
                BenchmarkResult(challenge_id="c2", category="malware", difficulty="h",
                               status="failed", flag_result="FAIL",
                               failure_reason="missing pe analysis",
                               failure_category="missing_skill"),
            ]
            entries = learner.learn_from_results(results)
            assert len(entries) == 2

    def test_get_improvement_summary(self):
        with _isolated_learner() as learner:
            r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m",
                               status="failed", flag_result="FAIL",
                               failure_reason="missing skill",
                               failure_category="missing_skill")
            learner.learn_from_result(r)
            summary = learner.get_improvement_summary()
            assert summary["total_challenges_processed"] >= 1

    def test_failure_updates_memory(self):
        with _isolated_learner() as learner:
            r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="h",
                               status="failed", flag_result="FAIL",
                               failure_reason="missing RSA skill",
                               failure_category="missing_skill")
            entry = learner.learn_from_result(r)
            assert entry.get("failure_analysis") is not None
            assert entry.get("skill_gaps") is not None


# ===================================================================
# FeedbackCollector
# ===================================================================

class TestFeedbackCollector:
    def test_collect(self):
        fc = FeedbackCollector()
        r = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m",
                           status="solved", flag_result="PASS", confidence=0.8,
                           execution_time=5.2)
        entry = fc.collect(r, "Good performance")
        assert entry["challenge_id"] == "c1"
        assert entry["notes"] == "Good performance"

    def test_get_feedback_by_category(self):
        fc = FeedbackCollector()
        fc.collect(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m", status="solved"))
        fc.collect(BenchmarkResult(challenge_id="w1", category="web", difficulty="m", status="failed"))
        crypto = fc.get_feedback(category="crypto")
        assert len(crypto) == 1

    def test_get_feedback_by_status(self):
        fc = FeedbackCollector()
        fc.collect(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m", status="solved"))
        fc.collect(BenchmarkResult(challenge_id="w1", category="web", difficulty="m", status="failed"))
        solved = fc.get_feedback(status="solved")
        assert len(solved) == 1

    def test_get_summary(self):
        fc = FeedbackCollector()
        fc.collect(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m", status="solved"))
        fc.collect(BenchmarkResult(challenge_id="w1", category="web", difficulty="m", status="failed"))
        summary = fc.get_summary()
        assert summary["total"] == 2
        assert summary["solved"] == 1

    def test_clear(self):
        fc = FeedbackCollector()
        fc.collect(BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="solved"))
        fc.clear()
        assert fc.get_summary()["total"] == 0


# ===================================================================
# KnowledgeUpdater
# ===================================================================

class TestKnowledgeUpdater:
    def test_update_solved(self):
        with _isolated_updater() as updater:
            entry = {
                "challenge_id": "c1",
                "category": "crypto",
                "status": "solved",
                "actions_taken": ["recorded_solution"],
            }
            result = updater.update_from_learning(entry)
            assert "solution_memory_updated" in result["updates"]

    def test_update_with_skill_gaps(self):
        with _isolated_updater() as updater:
            entry = {
                "challenge_id": "c1",
                "category": "malware",
                "status": "failed",
                "actions_taken": ["detected_skill_gaps", "evolved_strategy"],
                "skill_gaps": {"gaps": ["pe-analysis"], "confidence": 0.85},
                "evolved_strategy": ["Use PE analysis tools"],
            }
            result = updater.update_from_learning(entry)
            assert "skill_proposal" in " ".join(result["updates"])
            assert "strategy_memory_evolved" in result["updates"]

    def test_get_update_history(self):
        with _isolated_updater() as updater:
            entry = {"challenge_id": "c1", "category": "c", "status": "solved", "actions_taken": []}
            updater.update_from_learning(entry)
            history = updater.get_update_history()
            assert len(history) == 1

    def test_get_skill_proposals(self):
        with _isolated_updater() as updater:
            entry = {
                "challenge_id": "c1",
                "category": "malware",
                "status": "failed",
                "actions_taken": ["detected_skill_gaps"],
                "skill_gaps": {"gaps": ["pe-analysis"], "confidence": 0.8},
            }
            updater.update_from_learning(entry)
            proposals = updater.get_skill_proposals()
            assert len(proposals) >= 1

    def test_clear(self):
        with _isolated_updater() as updater:
            entry = {"challenge_id": "c1", "category": "c", "status": "solved", "actions_taken": []}
            updater.update_from_learning(entry)
            updater.clear()
            assert updater.get_update_history() == []


# ===================================================================
# Competition Mode
# ===================================================================

class TestScorer:
    def test_calculate_score(self):
        scorer = Scorer()
        r1 = BenchmarkResult(challenge_id="c1", category="crypto", difficulty="medium",
                            status="solved")
        r1.metadata = {"points": 300}
        results = [
            r1,
            BenchmarkResult(challenge_id="c2", category="web", difficulty="medium",
                           status="failed"),
        ]
        entry = scorer.calculate_score("team_a", results, total_time=120.0)
        assert entry.team_name == "team_a"
        assert entry.solved == 1
        assert entry.total_score == 300

    def test_rank_entries(self):
        scorer = Scorer()
        e1 = ScoreEntry(team_name="A", total_score=500, solved=3, total_time=100)
        e2 = ScoreEntry(team_name="B", total_score=800, solved=4, total_time=200)
        ranked = scorer.rank_entries([e1, e2])
        assert ranked[0].team_name == "B"


class TestLeaderboard:
    def test_record_and_get_rankings(self):
        with tempfile.TemporaryDirectory() as td:
            lb = Leaderboard(storage_dir=td)
            lb.record(ScoreEntry(team_name="TeamA", total_score=500, solved=3, total_time=100))
            lb.record(ScoreEntry(team_name="TeamB", total_score=800, solved=4, total_time=200))
            rankings = lb.get_rankings()
            assert len(rankings) == 2
            assert rankings[0]["team_name"] == "TeamB"

    def test_get_team(self):
        with tempfile.TemporaryDirectory() as td:
            lb = Leaderboard(storage_dir=td)
            lb.record(ScoreEntry(team_name="TeamA", total_score=500, solved=3))
            team = lb.get_team("TeamA")
            assert team is not None
            assert team.total_score == 500

    def test_get_team_missing(self):
        with tempfile.TemporaryDirectory() as td:
            lb = Leaderboard(storage_dir=td)
            assert lb.get_team("Nonexistent") is None

    def test_clear(self):
        with tempfile.TemporaryDirectory() as td:
            lb = Leaderboard(storage_dir=td)
            lb.record(ScoreEntry(team_name="A", total_score=100, solved=1))
            lb.clear()
            assert lb.get_rankings() == []


class TestCompetitionRunner:
    @pytest.mark.asyncio
    async def test_run_competition(self):
        async def fake_runner(cid: str) -> BenchmarkResult:
            r = BenchmarkResult(challenge_id=cid, category="crypto", difficulty="medium",
                               status="solved")
            r.metadata = {"points": 300}
            return r
        runner = CompetitionRunner(challenge_runner=fake_runner)
        result = await runner.run_competition(["c1", "c2"], "TestTeam")
        assert result["team"] == "TestTeam"
        assert result["challenges_solved"] == 2
        assert result["total_score"] == 600

    @pytest.mark.asyncio
    async def test_competition_with_failures(self):
        call_count = 0

        async def flaky_runner(cid: str) -> BenchmarkResult:
            nonlocal call_count
            call_count += 1
            r = BenchmarkResult(challenge_id=cid, category="crypto", difficulty="hard",
                               status="failed" if call_count < 2 else "solved")
            if call_count >= 2:
                r.metadata = {"points": 500}
            return r
        runner = CompetitionRunner(challenge_runner=flaky_runner,
                                   config=CompetitionRunner.__module__)  # just use default
        from competition.runner import CompetitionConfig
        runner.config = CompetitionConfig(max_attempts_per_challenge=3)
        result = await runner.run_competition(["c1"], "FlakyTeam")
        assert result["challenges_total"] == 1

    @pytest.mark.asyncio
    async def test_leaderboard_updates(self):
        async def fake_runner(cid: str) -> BenchmarkResult:
            r = BenchmarkResult(challenge_id=cid, category="crypto", difficulty="medium",
                               status="solved")
            r.metadata = {"points": 300}
            return r
        runner = CompetitionRunner(challenge_runner=fake_runner)
        result = await runner.run_competition(["c1"], "ScoreTeam")
        assert result["leaderboard"] is not None


# ===================================================================
# ImprovementReportGenerator
# ===================================================================

class TestImprovementReportGenerator:
    def test_generate_with_metrics(self):
        with _isolated_report_generator() as generator:
            prev_mc = MetricsCollector()
            prev_mc.record(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m", status="solved"))
            prev_mc.record(BenchmarkResult(challenge_id="c2", category="crypto", difficulty="m", status="failed"))

            curr_mc = MetricsCollector()
            curr_mc.record(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m", status="solved"))
            curr_mc.record(BenchmarkResult(challenge_id="c2", category="crypto", difficulty="m", status="solved"))

            report = generator.generate(previous_metrics=prev_mc, current_metrics=curr_mc)
            assert report.previous_success_rate == 0.5
            assert report.current_success_rate == 1.0
            assert report.improvement_delta == 0.5

    def test_generate_without_metrics(self):
        with _isolated_report_generator() as generator:
            report = generator.generate()
            assert report.previous_success_rate == 0.0

    def test_improvements_list(self):
        with _isolated_report_generator() as generator:
            prev_mc = MetricsCollector()
            curr_mc = MetricsCollector()
            prev_mc.record(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m", status="failed"))
            curr_mc.record(BenchmarkResult(challenge_id="c1", category="crypto", difficulty="m", status="solved"))
            report = generator.generate(prev_mc, curr_mc)
            assert len(report.improvements_made) >= 1

    def test_to_dict(self):
        with _isolated_report_generator() as generator:
            prev = MetricsCollector()
            curr = MetricsCollector()
            prev.record(BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="failed"))
            curr.record(BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="solved"))
            report = generator.generate(prev, curr)
            d = report.to_dict()
            assert d["improvement_delta"] == 1.0

    def test_summary_table(self):
        with _isolated_report_generator() as generator:
            prev = MetricsCollector()
            curr = MetricsCollector()
            prev.record(BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="failed"))
            curr.record(BenchmarkResult(challenge_id="c1", category="c", difficulty="m", status="solved"))
            report = generator.generate(prev, curr)
            table = report.summary_table()
            assert "Autonomous Improvement Report" in table
            assert "Improvement Delta" in table


# ===================================================================
# Backward Compatibility
# ===================================================================

class TestBackwardCompatibility:
    def test_retry_controller_unchanged(self):
        """Standard RetryController API unchanged."""
        ctrl = RetryController()
        assert ctrl.max_attempts == 3
        ctrl.register_failure("c1", {"category": "missing_skill"})
        strategy = ctrl.get_strategy("c1", 2)
        assert strategy["action"] == "retry"
        assert ctrl.total_failures == 1
