"""Tests for the LearningReportGenerator and LearningReport model."""

import json

import pytest
from pydantic import ValidationError

from learning.report import LearningReport, LearningReportGenerator
from agents.verifier import (
    Finding,
    VerificationAgent,
    VerificationResult,
    VerificationStatus,
)


# ---------------------------------------------------------------------------
# LearningReport model tests
# ---------------------------------------------------------------------------

class TestLearningReport:
    def test_minimal(self):
        lr = LearningReport(
            challenge_id="abc123",
            challenge_summary="Test challenge",
            skills_used=[],
            skills_mastered=[],
            skills_needing_improvement=[],
            learning_objectives=[],
            recommendations=[],
            difficulty_estimate="beginner",
        )
        assert lr.challenge_id == "abc123"
        assert lr.difficulty_estimate == "beginner"
        assert lr.student_report == ""
        assert lr.instructor_summary == ""

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            LearningReport()

    def test_roundtrip(self):
        lr = LearningReport(
            challenge_id="id123",
            challenge_summary="summary",
            skills_used=[{"name": "web-skill", "category": "web"}],
            skills_mastered=["web-skill"],
            skills_needing_improvement=[],
            learning_objectives=["Learn web"],
            recommendations=["Practice more"],
            difficulty_estimate="intermediate",
            student_report="Student text",
            instructor_summary="Instructor text",
        )
        d = lr.model_dump()
        assert d["challenge_id"] == "id123"
        assert len(d["skills_used"]) == 1
        restored = LearningReport(**d)
        assert restored.student_report == "Student text"


# ---------------------------------------------------------------------------
# LearningReportGenerator tests
# ---------------------------------------------------------------------------

class TestLearningReportGenerator:
    def make_skills(self, names=None):
        if names is None:
            names = ["web-xss", "forensics-pcap"]
        return [
            {"name": n, "description": f"Skill for {n}", "category": n.split("-")[0], "subdomain": n.split("-")[1] if "-" in n else n}
            for n in names
        ]

    def make_results(self, statuses=None):
        if statuses is None:
            statuses = [("completed", "Found evidence of the attack")]
        return [
            {"step": i, "agent": f"agent-{i}", "status": s, "response": r}
            for i, (s, r) in enumerate(statuses)
        ]

    def make_verification(self, confidence=0.9, findings=None):
        if findings is None:
            findings = [Finding(step_index=0, agent_name="agent-0", finding_type="flag_format", severity="info", message="flag{test}")]
        return VerificationResult(
            status=VerificationStatus.PASSED if confidence >= 0.8 else VerificationStatus.NEEDS_REVIEW,
            confidence_score=confidence,
            findings=findings,
            issues=[f.message for f in findings if f.severity == "error"],
            recommendations=[],
        )

    # --- Basic generation ---

    def test_generates_successful_challenge_report(self):
        gen = LearningReportGenerator()
        skills = self.make_skills()
        results = self.make_results()
        vr = self.make_verification(confidence=0.95)

        report = gen.generate(
            request="Find the XSS vulnerability and extract the flag",
            skills_used=skills,
            verification_result=vr,
            agent_results=results,
        )
        assert report.challenge_id is not None
        assert len(report.challenge_id) == 12
        assert report.difficulty_estimate in ("beginner", "intermediate", "advanced")
        assert len(report.skills_used) == 2
        assert len(report.learning_objectives) == 2
        assert report.student_report != ""
        assert report.instructor_summary != ""

    def test_generates_failed_challenge_report(self):
        gen = LearningReportGenerator()
        skills = self.make_skills()
        results = self.make_results([("failed", "Error: timeout")])
        vr = self.make_verification(
            confidence=0.2,
            findings=[Finding(step_index=0, agent_name="agent-0", finding_type="execution_failure", severity="error", message="Step failed")],
        )

        report = gen.generate(
            request="Exploit the buffer overflow",
            skills_used=skills,
            verification_result=vr,
            agent_results=results,
        )
        assert report.verification_result is not None
        assert report.verification_result["confidence_score"] == 0.2
        assert len(report.skills_needing_improvement) >= 1

    def test_missing_skills(self):
        gen = LearningReportGenerator()
        report = gen.generate(
            request="Simple test",
            skills_used=[],
            agent_results=self.make_results(),
        )
        assert len(report.skills_used) == 0
        assert len(report.learning_objectives) == 1  # default objective
        assert report.student_report != ""

    def test_no_verification_result(self):
        gen = LearningReportGenerator()
        skills = self.make_skills(["web-xss"])
        report = gen.generate(
            request="Test without verification",
            skills_used=skills,
            agent_results=self.make_results(),
        )
        assert report.verification_result is None
        assert len(report.skills_mastered) == 1  # all skills classified as mastered

    # --- Skill tracking ---

    def test_skills_used_are_recorded(self):
        gen = LearningReportGenerator()
        skills = self.make_skills(["web-xss", "forensics-pcap", "reverse-engineering"])
        results = self.make_results()
        vr = self.make_verification(confidence=0.9)

        report = gen.generate(
            request="Multi-skill challenge",
            skills_used=skills,
            verification_result=vr,
            agent_results=results,
        )
        assert len(report.skills_used) == 3
        names = {s["name"] for s in report.skills_used}
        assert "web-xss" in names
        assert "forensics-pcap" in names
        assert "reverse-engineering" in names

    def test_skills_mastered_vs_needing(self):
        gen = LearningReportGenerator()
        skills = self.make_skills(["web-xss", "forensics-pcap"])
        results = self.make_results([("completed", "flag{found}"), ("failed", "error")])
        vr = self.make_verification(
            confidence=0.4,
            findings=[
                Finding(step_index=0, agent_name="agent-0", finding_type="flag_format", severity="info", message="flag{found}"),
                Finding(step_index=1, agent_name="agent-1", finding_type="execution_failure", severity="error", message="step 1 failed"),
            ],
        )

        report = gen.generate(
            request="Test skill classification",
            skills_used=skills,
            verification_result=vr,
            agent_results=results,
        )
        # With low confidence (0.4) and errors, skills go to needing
        assert len(report.skills_needing_improvement) >= 1

    # --- Verification failure ---

    def test_verification_failure_reflected(self):
        gen = LearningReportGenerator()
        skills = self.make_skills(["web-xss"])
        results = self.make_results([("completed", "")])
        vr = self.make_verification(
            confidence=0.0,
            findings=[Finding(step_index=0, agent_name="agent-0", finding_type="empty_response", severity="error", message="empty")],
        )

        report = gen.generate(
            request="Empty result test",
            skills_used=skills,
            verification_result=vr,
            agent_results=results,
        )
        assert report.verification_result["confidence_score"] == 0.0
        assert report.difficulty_estimate == "advanced"  # very low confidence
        assert len(report.recommendations) >= 1

    # --- Report format content ---

    def test_student_report_includes_sections(self):
        gen = LearningReportGenerator()
        skills = self.make_skills(["web-xss"])
        results = self.make_results()
        vr = self.make_verification(confidence=0.9)

        report = gen.generate(
            request="Test student report",
            skills_used=skills,
            verification_result=vr,
            agent_results=results,
        )
        sr = report.student_report
        assert "LEARNING REPORT" in sr
        assert "Skills Practiced" in sr
        assert "Learning Objectives" in sr
        assert "Improvement Suggestions" in sr
        assert "web-xss" in sr

    def test_instructor_summary_includes_sections(self):
        gen = LearningReportGenerator()
        skills = self.make_skills(["web-xss"])
        results = self.make_results()
        vr = self.make_verification(confidence=0.95)

        report = gen.generate(
            request="Test instructor report",
            skills_used=skills,
            verification_result=vr,
            agent_results=results,
        )
        ins = report.instructor_summary
        assert "INSTRUCTOR SUMMARY" in ins
        assert "Skills Used" in ins
        assert "Skills Mastered" in ins
        assert "Training Recommendations" in ins
        assert report.challenge_id in ins

    # --- Edge cases ---

    def test_empty_request(self):
        gen = LearningReportGenerator()
        report = gen.generate(request="")
        assert report.challenge_id is not None
        assert report.student_report != ""

    def test_large_number_of_skills(self):
        gen = LearningReportGenerator()
        skills = self.make_skills([f"skill-{i}" for i in range(20)])
        results = self.make_results([("completed", "ok") for _ in range(5)])
        vr = self.make_verification(confidence=0.85)

        report = gen.generate(
            request="Many skills test",
            skills_used=skills,
            verification_result=vr,
            agent_results=results,
        )
        assert len(report.skills_used) == 20
        assert len(report.learning_objectives) == 20

    def test_difficulty_estimate_by_steps(self):
        gen = LearningReportGenerator()
        # 5 steps → advanced
        results = self.make_results([("completed", "ok") for _ in range(5)])
        report = gen.generate(
            request="Hard challenge",
            skills_used=self.make_skills(["web-xss"]),
            agent_results=results,
        )
        assert report.difficulty_estimate == "advanced"

    def test_difficulty_estimate_beginner(self):
        gen = LearningReportGenerator()
        # 1 step → beginner
        results = self.make_results([("completed", "ok")])
        report = gen.generate(
            request="Easy challenge",
            skills_used=self.make_skills(["web-xss"]),
            agent_results=results,
        )
        assert report.difficulty_estimate == "beginner"

    def test_recommendations_for_failed_execution(self):
        gen = LearningReportGenerator()
        results = self.make_results([("failed", "crash")])
        vr = self.make_verification(
            confidence=0.1,
            findings=[Finding(step_index=0, agent_name="agent-0", finding_type="execution_failure", severity="error", message="failed")],
        )

        report = gen.generate(
            request="Failure report",
            skills_used=self.make_skills(["web-xss"]),
            verification_result=vr,
            agent_results=results,
        )
        assert len(report.recommendations) >= 1

    def test_challenge_id_is_deterministic(self):
        gen = LearningReportGenerator()
        r1 = gen.generate(request="Deterministic test")
        r2 = gen.generate(request="Deterministic test")
        assert r1.challenge_id == r2.challenge_id

    def test_challenge_id_differs_for_different_requests(self):
        gen = LearningReportGenerator()
        r1 = gen.generate(request="First request")
        r2 = gen.generate(request="Second request")
        assert r1.challenge_id != r2.challenge_id

    # --- Supervisor integration ---

    def test_supervisor_delegates_to_report_generator(self):
        from models.llm import LLM, LLMResponse, LLMUsage
        from agents.registry import AgentRegistry
        from agents.supervisor import SupervisorAgent
        from core.specialized import SpecializedAgent

        class FakeLLM(LLM):
            def __init__(self):
                self.plan = '{"analysis": "test", "steps": [{"agent": "tester", "task": "find flag", "depends_on": []}]}'
            async def chat(self, messages, **kwargs):
                content = self.plan
                if any(m.get("content","") for m in messages if m["role"] == "user"):
                    content = "Final answer."
                return LLMResponse(content=content, usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))

        class EchoAgent(SpecializedAgent):
            def __init__(self, llm):
                super().__init__(name="tester", llm=llm, system_prompt="test")
            async def process_task(self, task):
                return "flag{found} with evidence."

        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        rg = LearningReportGenerator()
        verifier = VerificationAgent()
        supervisor = SupervisorAgent(llm, registry, verifier=verifier, report_generator=rg)

        import asyncio
        result = asyncio.run(supervisor.run("Find the flag"))
        assert result["learning_report"] is not None
        assert "challenge_id" in result["learning_report"]
        assert "student_report" in result["learning_report"]
        assert "instructor_summary" in result["learning_report"]
        assert result["final_response"] != ""

    def test_learning_report_included_in_synthesis_prompt(self):
        from models.llm import LLM, LLMResponse, LLMUsage
        from agents.registry import AgentRegistry
        from agents.supervisor import SupervisorAgent
        from core.specialized import SpecializedAgent

        class CaptureLLM(LLM):
            def __init__(self):
                self.last_user_content = ""
                self.plan = '{"analysis": "test", "steps": [{"agent": "tester", "task": "do it", "depends_on": []}]}'
            async def chat(self, messages, **kwargs):
                for m in messages:
                    if m["role"] == "user":
                        self.last_user_content = m["content"]
                return LLMResponse(content="ok", usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))

        class EchoAgent(SpecializedAgent):
            def __init__(self, llm):
                super().__init__(name="tester", llm=llm, system_prompt="test")
            async def process_task(self, task):
                return "Result with evidence."

        llm = CaptureLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        rg = LearningReportGenerator()
        supervisor = SupervisorAgent(llm, registry, report_generator=rg)

        import asyncio
        asyncio.run(supervisor.run("Test learning report synthesis"))
        assert "Learning Report" in llm.last_user_content or "learning_report" in llm.last_user_content

    def test_supervisor_without_report_generator_still_works(self):
        from models.llm import LLM, LLMResponse, LLMUsage
        from agents.registry import AgentRegistry
        from agents.supervisor import SupervisorAgent

        class FakeLLM(LLM):
            async def chat(self, messages, **kwargs):
                return LLMResponse(content='{"analysis": "test", "steps": []}', usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))

        llm = FakeLLM()
        registry = AgentRegistry()
        supervisor = SupervisorAgent(llm, registry)
        import asyncio
        result = asyncio.run(supervisor.run("test"))
        assert "learning_report" not in result or result["learning_report"] is None

    def test_learning_report_template_exists(self):
        from agents.supervisor import LEARNING_REPORT_PROMPT_SECTION
        assert "{learning_report}" in LEARNING_REPORT_PROMPT_SECTION
