"""Tests for the CTF Challenge Orchestration and Evaluation Framework.

Covers:
  - Challenge Loading and discovery
  - Challenge Registry search/filter
  - Challenge Validation
  - Flag Verification (exact, regex, evidence)
  - Pipeline integration with SupervisorAgent
  - Learning report enhancement
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from challenges_engine.loader import ChallengeLoader
from challenges_engine.models import ChallengeDefinition
from challenges_engine.registry import ChallengeRegistry
from challenges_engine.validator import ChallengeValidator, ValidationResult
from challenges_engine.verifier import FlagVerifier, FlagStatus

from models.llm import LLM, LLMResponse, LLMUsage
from agents.registry import AgentRegistry
from agents.supervisor import SupervisorAgent
from core.specialized import SpecializedAgent
from skills_engine.planner import SkillPlanner
from skills_engine.execution import ExecutionAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_challenge_yaml(tmp_dir: Path, challenge_id: str, overrides: dict = None) -> Path:
    c_dir = tmp_dir / challenge_id
    (c_dir / "files").mkdir(parents=True, exist_ok=True)
    (c_dir / "hints").mkdir(parents=True, exist_ok=True)
    (c_dir / "expected").mkdir(parents=True, exist_ok=True)

    (c_dir / "expected" / "flag.txt").write_text("CTF{test_flag}")
    (c_dir / "hints" / "hint1.txt").write_text("Look at the metadata")

    data = {
        "name": overrides.get("name", challenge_id) if overrides else challenge_id,
        "category": overrides.get("category", "steganography") if overrides else "steganography",
        "difficulty": overrides.get("difficulty", "beginner") if overrides else "beginner",
        "description": overrides.get("description", f"A test challenge called {challenge_id}") if overrides else f"A test challenge called {challenge_id}",
        "required_skills": overrides.get("required_skills", ["steganography-basics"]) if overrides else ["steganography-basics"],
        "allowed_tools": overrides.get("allowed_tools", ["strings", "exiftool"]) if overrides else ["strings", "exiftool"],
        "verification": overrides.get("verification", {"type": "exact_flag"}) if overrides else {"type": "exact_flag"},
        "flag_format": overrides.get("flag_format", "CTF{.*}") if overrides else "CTF{.*}",
        "expected_flag": overrides.get("expected_flag", "CTF{test_flag}") if overrides else "CTF{test_flag}",
    }

    with open(c_dir / "challenge.yaml", "w") as f:
        yaml.dump(data, f)

    (c_dir / "files" / "image.png").write_text("fake png content")
    return c_dir


# ===================================================================
# Challenge Loading
# ===================================================================

class TestChallengeLoading:
    def test_discovers_valid_challenges(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            create_challenge_yaml(d, "test-challenge-1")
            create_challenge_yaml(d, "test-challenge-2")
            loader = ChallengeLoader(challenges_dir=str(d))
            discovered = loader.discover()
            assert "test-challenge-1" in discovered
            assert "test-challenge-2" in discovered
            assert len(discovered) == 2

    def test_loads_valid_challenge(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            create_challenge_yaml(d, "test-challenge")
            loader = ChallengeLoader(challenges_dir=str(d))
            challenge = loader.load("test-challenge")
            assert challenge is not None
            assert challenge.name == "test-challenge"
            assert challenge.category == "steganography"
            assert challenge.difficulty == "beginner"
            assert len(challenge.hints) == 1
            assert len(challenge.files) == 1

    def test_invalid_yaml_handled_gracefully(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            c_dir = d / "bad-challenge"
            c_dir.mkdir()
            (c_dir / "challenge.yaml").write_text("not: valid: yaml: [[[")
            loader = ChallengeLoader(challenges_dir=str(d))
            challenge = loader.load("bad-challenge")
            assert challenge is None

    def test_missing_challenge_yaml_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "empty-dir").mkdir()
            loader = ChallengeLoader(challenges_dir=str(d))
            challenge = loader.load("empty-dir")
            assert challenge is None

    def test_nonexistent_directory_returns_empty(self):
        loader = ChallengeLoader(challenges_dir=r"C:\nonexistent_challenge_dir")
        discovered = loader.discover()
        assert discovered == []

    def test_load_all_returns_all_valid(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            create_challenge_yaml(d, "challenge-a")
            create_challenge_yaml(d, "challenge-b")
            loader = ChallengeLoader(challenges_dir=str(d))
            loaded = loader.load_all()
            assert len(loaded) == 2
            names = {c.name for c in loaded}
            assert "challenge-a" in names
            assert "challenge-b" in names


# ===================================================================
# Challenge Registry
# ===================================================================

class TestChallengeRegistry:
    @pytest.fixture
    def registry(self):
        r = ChallengeRegistry()
        r.register(ChallengeDefinition(
            name="Stego Challenge",
            category="steganography",
            difficulty="beginner",
            description="Extract hidden data from image",
            required_skills=["steganography-basics"],
            allowed_tools=["strings", "exiftool"],
            expected_flag="CTF{test}",
        ))
        r.register(ChallengeDefinition(
            name="Malware Analysis",
            category="malware",
            difficulty="intermediate",
            description="Analyze suspicious binary",
            required_skills=["malware-analysis-basics"],
            allowed_tools=["strings", "file"],
            expected_flag="CTF{test2}",
        ))
        r.register(ChallengeDefinition(
            name="Web SQL Injection",
            category="web_security",
            difficulty="beginner",
            description="Find SQL injection vulnerability",
            required_skills=["web-security-basics"],
            allowed_tools=["curl"],
            expected_flag="CTF{test3}",
        ))
        return r

    def test_lookup_works(self, registry):
        c = registry.get("stego-challenge")
        assert c is not None
        assert c.category == "steganography"

    def test_lookup_missing_returns_none(self, registry):
        c = registry.get("nonexistent")
        assert c is None

    def test_search_by_category(self, registry):
        results = registry.search(category="malware")
        assert len(results) == 1
        assert results[0].name == "Malware Analysis"

    def test_search_by_difficulty(self, registry):
        results = registry.search(difficulty="beginner")
        assert len(results) == 2

    def test_search_by_skill(self, registry):
        results = registry.search(required_skill="malware")
        assert len(results) == 1

    def test_search_multiple_filters(self, registry):
        results = registry.search(category="web_security", difficulty="beginner")
        assert len(results) == 1
        assert results[0].name == "Web SQL Injection"

    def test_search_no_match(self, registry):
        results = registry.search(category="forensics")
        assert results == []

    def test_list_categories(self, registry):
        cats = registry.list_categories()
        assert "steganography" in cats
        assert "malware" in cats
        assert "web_security" in cats

    def test_contains(self, registry):
        assert "stego-challenge" in registry
        assert "nonexistent" not in registry

    def test_len(self, registry):
        assert len(registry) == 3


# ===================================================================
# Challenge Validation
# ===================================================================

class TestChallengeValidation:
    def test_valid_challenge_passes(self):
        challenge = ChallengeDefinition(
            name="Test Challenge",
            category="steganography",
            difficulty="beginner",
            description="A test challenge",
            required_skills=["test-skill"],
            allowed_tools=["strings"],
            expected_flag="CTF{test}",
        )
        validator = ChallengeValidator()
        result = validator.validate(challenge)
        assert result.is_valid

    def test_missing_name_flagged(self):
        challenge = ChallengeDefinition(
            name="",
            category="steganography",
            difficulty="beginner",
            description="Test",
            expected_flag="CTF{test}",
        )
        validator = ChallengeValidator()
        result = validator.validate(challenge)
        assert not result.is_valid
        assert any(e.field == "name" for e in result.errors)

    def test_invalid_category_flagged(self):
        challenge = ChallengeDefinition(
            name="Test",
            category="invalid_category",
            difficulty="beginner",
            description="Test",
            expected_flag="CTF{test}",
        )
        validator = ChallengeValidator()
        result = validator.validate(challenge)
        assert not result.is_valid
        assert any(e.field == "category" for e in result.errors)

    def test_invalid_difficulty_flagged(self):
        challenge = ChallengeDefinition(
            name="Test",
            category="steganography",
            difficulty="extreme",
            description="Test",
            expected_flag="CTF{test}",
        )
        validator = ChallengeValidator()
        result = validator.validate(challenge)
        assert not result.is_valid
        assert any(e.field == "difficulty" for e in result.errors)

    def test_missing_expected_flag_flagged(self):
        challenge = ChallengeDefinition(
            name="Test",
            category="steganography",
            difficulty="beginner",
            description="Test",
        )
        validator = ChallengeValidator()
        result = validator.validate(challenge)
        assert not result.is_valid
        assert any(e.field == "expected_flag" for e in result.errors)

    def test_none_challenge_flagged(self):
        validator = ChallengeValidator()
        result = validator.validate(None)
        assert not result.is_valid

    def test_validation_result_bool(self):
        r = ValidationResult()
        assert r.is_valid
        assert bool(r) is True
        r.add_error("test", "error")
        assert not r.is_valid
        assert bool(r) is False


# ===================================================================
# Flag Verification
# ===================================================================

class TestFlagVerifier:
    def test_exact_match_passes(self):
        challenge = ChallengeDefinition(
            name="Test", category="steganography", difficulty="beginner",
            description="Test", expected_flag="CTF{hello_world}",
            verification={"type": "exact_flag"},
        )
        verifier = FlagVerifier()
        result = verifier.verify(challenge, agent_response="The flag is CTF{hello_world}")
        assert result.status == FlagStatus.PASS
        assert result.method == "exact_flag"

    def test_exact_match_fails(self):
        challenge = ChallengeDefinition(
            name="Test", category="steganography", difficulty="beginner",
            description="Test", expected_flag="CTF{correct_flag}",
            verification={"type": "exact_flag"},
        )
        verifier = FlagVerifier()
        result = verifier.verify(challenge, agent_response="The flag is CTF{wrong_flag}")
        assert result.status == FlagStatus.FAIL

    def test_regex_match_passes(self):
        challenge = ChallengeDefinition(
            name="Test", category="steganography", difficulty="beginner",
            description="Test", expected_flag="CTF{abc123}",
            flag_format=r"CTF\{.*\}",
            verification={"type": "regex"},
        )
        verifier = FlagVerifier()
        result = verifier.verify(challenge, agent_response="Found flag: CTF{abc123}")
        assert result.status == FlagStatus.PASS
        assert result.method == "regex"

    def test_regex_no_match_fails(self):
        challenge = ChallengeDefinition(
            name="Test", category="steganography", difficulty="beginner",
            description="Test", expected_flag="CTF{target}",
            flag_format=r"CTF\{.*\}",
            verification={"type": "regex"},
        )
        verifier = FlagVerifier()
        result = verifier.verify(challenge, agent_response="No flag found")
        assert result.status == FlagStatus.FAIL

    def test_evidence_match_from_tool_output(self):
        challenge = ChallengeDefinition(
            name="Test", category="steganography", difficulty="beginner",
            description="Test", expected_flag="CTF{from_tools}",
            verification={"type": "evidence"},
        )
        verifier = FlagVerifier()
        tool_outputs = [
            {"tool": "strings", "output": "some text\nCTF{from_tools}\nmore text"},
        ]
        result = verifier.verify(challenge, agent_response="", tool_outputs=tool_outputs)
        assert result.status == FlagStatus.PASS
        assert result.method == "evidence"

    def test_evidence_no_match_fails(self):
        challenge = ChallengeDefinition(
            name="Test", category="steganography", difficulty="beginner",
            description="Test", expected_flag="CTF{missing}",
            verification={"type": "evidence"},
        )
        verifier = FlagVerifier()
        tool_outputs = [{"tool": "strings", "output": "nothing relevant"}]
        result = verifier.verify(challenge, agent_response="Done", tool_outputs=tool_outputs)
        assert result.status == FlagStatus.FAIL

    def test_missing_expected_flag_returns_error(self):
        challenge = ChallengeDefinition(
            name="Test", category="steganography", difficulty="beginner",
            description="Test",
        )
        verifier = FlagVerifier()
        result = verifier.verify(challenge, agent_response="CTF{something}")
        assert result.status == FlagStatus.ERROR

    def test_empty_challenge_returns_error(self):
        verifier = FlagVerifier()
        result = verifier.verify(None, agent_response="")
        assert result.status == FlagStatus.ERROR


# ===================================================================
# Pipeline Integration
# ===================================================================

class FakeLLM(LLM):
    def __init__(self):
        self.plan_response = json.dumps({
            "analysis": "Analyze the challenge using appropriate tools.",
            "steps": [
                {"agent": "analyst", "task": "Analyze the provided challenge and extract the flag.", "depends_on": []},
            ],
        })
        self.synthesis_response = "Challenge analysis complete. The evidence shows the flag was successfully extracted."

    async def chat(self, messages, **kwargs):
        user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
        is_planning = "synthesize" not in user_content.lower() and "agent results" not in user_content.lower()
        content = self.plan_response if is_planning else self.synthesis_response
        return LLMResponse(
            content=content,
            usage=LLMUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )


class ChallengeAgent(SpecializedAgent):
    def __init__(self, llm):
        super().__init__(name="analyst", llm=llm, system_prompt="You are a CTF challenge solver.")

    async def process_task(self, task: str) -> str:
        return "Based on the analysis, the evidence shows the flag is CTF{test_flag}. The challenge was solved successfully."


class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_challenge_loaded_before_pipeline(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            create_challenge_yaml(d, "stego_test", overrides={
                "expected_flag": "CTF{test_flag}",
                "verification": {"type": "exact_flag"},
            })
            loader = ChallengeLoader(challenges_dir=str(d))
            from challenges_engine.verifier import FlagVerifier

            llm = FakeLLM()
            agent_registry = AgentRegistry()
            agent_registry.register(ChallengeAgent(llm))
            planner = SkillPlanner(llm, agent_registry)
            execution_agent = ExecutionAgent(agent_registry)
            verifier = None
            supervisor = SupervisorAgent(
                llm, agent_registry,
                planner=planner,
                execution_agent=execution_agent,
                challenge_loader=loader,
                flag_verifier=FlagVerifier(),
            )

            result = await supervisor.run(
                "Solve the steganography challenge and find the hidden flag.",
                challenge_id="stego_test",
            )

            assert result["challenge"] is not None
            assert result["challenge"]["name"] == "stego_test"
            assert result["challenge"]["category"] == "steganography"
            assert result["flag_verification"] is not None
            assert result["flag_verification"]["status"] == "PASS"
            assert "final_response" in result

    @pytest.mark.asyncio
    async def test_supervisor_works_without_challenge_system(self):
        llm = FakeLLM()
        agent_registry = AgentRegistry()
        agent_registry.register(ChallengeAgent(llm))
        planner = SkillPlanner(llm, agent_registry)
        supervisor = SupervisorAgent(llm, agent_registry, planner=planner)

        result = await supervisor.run("Solve this challenge.")
        assert "final_response" in result
        assert result["challenge"] is None
        assert result["flag_verification"] is None

    @pytest.mark.asyncio
    async def test_challenge_context_injected_into_request(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            create_challenge_yaml(d, "web_test", overrides={
                "category": "web_security",
                "expected_flag": "CTF{web_flag}",
            })
            loader = ChallengeLoader(challenges_dir=str(d))
            from challenges_engine.verifier import FlagVerifier

            llm = FakeLLM()
            agent_registry = AgentRegistry()
            agent_registry.register(ChallengeAgent(llm))
            planner = SkillPlanner(llm, agent_registry)
            execution_agent = ExecutionAgent(agent_registry)
            supervisor = SupervisorAgent(
                llm, agent_registry,
                planner=planner,
                execution_agent=execution_agent,
                challenge_loader=loader,
                flag_verifier=FlagVerifier(),
            )

            result = await supervisor.run(
                "Find the vulnerability.",
                challenge_id="web_test",
            )

            assert result["challenge"] is not None
            assert result["challenge"]["category"] == "web_security"

    @pytest.mark.asyncio
    async def test_full_pipeline_contract_with_challenge(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            create_challenge_yaml(d, "full_test")
            loader = ChallengeLoader(challenges_dir=str(d))
            from challenges_engine.verifier import FlagVerifier

            llm = FakeLLM()
            agent_registry = AgentRegistry()
            agent_registry.register(ChallengeAgent(llm))
            planner = SkillPlanner(llm, agent_registry)
            execution_agent = ExecutionAgent(agent_registry)
            supervisor = SupervisorAgent(
                llm, agent_registry,
                planner=planner,
                execution_agent=execution_agent,
                challenge_loader=loader,
                flag_verifier=FlagVerifier(),
            )

            result = await supervisor.run("Solve it.", challenge_id="full_test")
            expected_keys = {
                "request", "analysis", "plan", "agent_results",
                "verification", "learning_report", "final_response",
                "flag_verification", "challenge",
            }
            assert set(result.keys()) == expected_keys


# ===================================================================
# Learning Report Enhancement
# ===================================================================

class TestLearningReportEnhancement:
    def test_challenge_info_in_report(self):
        from learning.report import LearningReportGenerator

        generator = LearningReportGenerator()
        report = generator.generate(
            request="Solve the challenge",
            challenge_info={"name": "Test Challenge", "category": "steganography", "difficulty": "beginner"},
            flag_result={"status": "PASS", "method": "exact_flag", "detail": "Flag matched"},
            tools_used=["strings", "exiftool"],
        )
        student = report.student_report
        assert "Test Challenge" in student
        assert "steganography" in student
        assert "PASS" in student
        assert "strings" in student
        assert "exiftool" in student

    def test_flag_result_in_instructor_summary(self):
        from learning.report import LearningReportGenerator

        generator = LearningReportGenerator()
        report = generator.generate(
            request="Analyze the binary",
            challenge_info={"name": "Malware Challenge", "category": "malware", "difficulty": "intermediate"},
            flag_result={"status": "FAIL", "method": "exact_flag", "detail": "No match"},
            tools_used=["file"],
        )
        instructor = report.instructor_summary
        assert "FAIL" in instructor
        assert "Malware Challenge" in instructor

    def test_challenge_category_in_training_recommendations(self):
        from learning.report import LearningReportGenerator

        generator = LearningReportGenerator()
        report = generator.generate(
            request="Extract the flag",
            challenge_info={"name": "Crypto", "category": "cryptography", "difficulty": "beginner"},
            flag_result={"status": "PASS", "method": "exact_flag", "detail": "OK"},
            tools_used=[],
        )
        assert "cryptography" in report.instructor_summary


# ===================================================================
# Production Challenge Loading
# ===================================================================

class TestProductionChallenges:
    def test_loads_all_production_challenges(self):
        loader = ChallengeLoader()
        all_challenges = loader.load_all()
        assert len(all_challenges) >= 5
        categories = {c.category for c in all_challenges}
        assert "steganography" in categories
        assert "malware" in categories
        assert "cryptography" in categories
        assert "web_security" in categories
        assert "forensics" in categories

    def test_production_challenges_validate(self):
        loader = ChallengeLoader()
        validator = ChallengeValidator()
        all_challenges = loader.load_all()
        for c in all_challenges:
            result = validator.validate(c)
            assert result.is_valid, f"Challenge '{c.name}' failed validation: {[e.message for e in result.errors]}"

    def test_production_challenges_have_expected_flags(self):
        loader = ChallengeLoader()
        all_challenges = loader.load_all()
        for c in all_challenges:
            assert c.expected_flag, f"Challenge '{c.name}' missing expected_flag"
            assert c.expected_flag.startswith("CTF{"), f"Challenge '{c.name}' flag doesn't start with CTF{{"
