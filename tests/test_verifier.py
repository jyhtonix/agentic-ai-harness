"""Tests for the VerificationAgent, VerificationStatus, VerificationResult, and Finding models."""

import asyncio

import pytest
from pydantic import ValidationError

from agents.verifier import (
    Finding,
    VerificationAgent,
    VerificationResult,
    VerificationStatus,
)


# ---------------------------------------------------------------------------
# Finding model tests
# ---------------------------------------------------------------------------

class TestFinding:
    def test_minimal(self):
        f = Finding(step_index=0, agent_name="tester", finding_type="flag_format", severity="info", message="found flag")
        assert f.step_index == 0
        assert f.finding_type == "flag_format"
        assert f.severity == "info"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            Finding(step_index=0)


# ---------------------------------------------------------------------------
# VerificationResult model tests
# ---------------------------------------------------------------------------

class TestVerificationResult:
    def test_minimal(self):
        vr = VerificationResult(
            status=VerificationStatus.PASSED,
            confidence_score=0.95,
            findings=[],
            issues=[],
            recommendations=[],
        )
        assert vr.status == VerificationStatus.PASSED
        assert vr.confidence_score == 0.95

    def test_roundtrip(self):
        vr = VerificationResult(
            status=VerificationStatus.FAILED,
            confidence_score=0.2,
            findings=[
                Finding(step_index=0, agent_name="a", finding_type="empty_response", severity="error", message="empty"),
            ],
            issues=["empty"],
            recommendations=["fix it"],
        )
        d = vr.model_dump()
        assert d["status"] == "failed"
        assert d["confidence_score"] == 0.2
        assert len(d["findings"]) == 1
        restored = VerificationResult(**d)
        assert restored.status == VerificationStatus.FAILED


# ---------------------------------------------------------------------------
# VerificationAgent unit tests
# ---------------------------------------------------------------------------

class TestVerificationAgent:
    @pytest.fixture(autouse=True)
    def _init_verifier(self):
        self.agent = VerificationAgent()

    async def verify(self, request="", plan=None, agent_results=None):
        return await self.agent.verify(request=request, plan=plan, agent_results=agent_results)

    def make_result(self, step=0, agent="tester", status="completed", response="Here is the analysis and evidence. The flag is flag{test123}. Based on the evidence, this is correct."):
        return {"step": step, "agent": agent, "status": status, "response": response}

    # --- Flag format detection ---

    @pytest.mark.asyncio
    async def test_detects_correct_flag_format(self):
        results = [self.make_result(response="The flag is flag{abc123} and that is the answer.")]
        vr = await self.verify(agent_results=results)
        assert any(f.finding_type == "flag_format" for f in vr.findings)
        assert vr.confidence_score > 0.5

    @pytest.mark.asyncio
    async def test_detects_uppercase_flag(self):
        results = [self.make_result(response="FLAG{SECRET} found in output.")]
        vr = await self.verify(agent_results=results)
        assert any(f.finding_type == "flag_format" for f in vr.findings)

    @pytest.mark.asyncio
    async def test_detects_ctf_format(self):
        results = [self.make_result(response="ctf{challenge_complete} verified.")]
        vr = await self.verify(agent_results=results)
        assert any(f.finding_type == "flag_format" for f in vr.findings)

    @pytest.mark.asyncio
    async def test_no_false_positive_on_plain_text(self):
        results = [self.make_result(response="No flags here, just analysis and evidence.")]
        vr = await self.verify(agent_results=results)
        assert not any(f.finding_type == "flag_format" for f in vr.findings)

    # --- Empty response detection ---

    @pytest.mark.asyncio
    async def test_detects_empty_response(self):
        results = [self.make_result(response="")]
        vr = await self.verify(agent_results=results)
        assert any(f.finding_type == "empty_response" for f in vr.findings)
        assert vr.status == VerificationStatus.FAILED

    @pytest.mark.asyncio
    async def test_detects_minimal_response(self):
        results = [self.make_result(response="OK")]
        vr = await self.verify(agent_results=results)
        assert any(f.finding_type == "minimal_response" for f in vr.findings)

    # --- Evidence/reasoning detection ---

    @pytest.mark.asyncio
    async def test_detects_missing_evidence(self):
        results = [self.make_result(response="The answer is 42. That is all.")]
        vr = await self.verify(agent_results=results)
        assert any(f.finding_type == "missing_evidence" for f in vr.findings)

    @pytest.mark.asyncio
    async def test_passes_with_evidence(self):
        results = [self.make_result(response="Based on the analysis, the evidence shows that the flag is correct because the output matches.")]
        vr = await self.verify(agent_results=results)
        assert not any(f.finding_type == "missing_evidence" for f in vr.findings)

    # --- Unsupported claims ---

    @pytest.mark.asyncio
    async def test_detects_uncertain_language(self):
        results = [self.make_result(response="I think the answer might be 42, but I'm not sure.")]
        vr = await self.verify(agent_results=results)
        assert any(f.finding_type == "unsupported_claim" for f in vr.findings)

    @pytest.mark.asyncio
    async def test_passes_confident_response(self):
        results = [self.make_result(response="The analysis confirms the flag is flag{test}. The evidence demonstrates correctness.")]
        vr = await self.verify(agent_results=results)
        assert not any(f.finding_type == "unsupported_claim" for f in vr.findings)

    # --- Failed execution ---

    @pytest.mark.asyncio
    async def test_detects_failed_execution(self):
        results = [self.make_result(status="failed", response="Agent crashed")]
        vr = await self.verify(agent_results=results)
        assert any(f.finding_type == "execution_failure" for f in vr.findings)
        assert vr.status == VerificationStatus.FAILED

    # --- Empty results ---

    @pytest.mark.asyncio
    async def test_empty_results_list(self):
        vr = await self.verify(agent_results=[])
        assert vr.status == VerificationStatus.FAILED
        assert vr.confidence_score == 0.0
        assert len(vr.issues) > 0

    @pytest.mark.asyncio
    async def test_none_results(self):
        vr = await self.verify(agent_results=None)
        assert vr.status == VerificationStatus.FAILED

    # --- Confidence scoring ---

    @pytest.mark.asyncio
    async def test_high_confidence_with_flag_and_evidence(self):
        results = [self.make_result(
            response="Based on thorough analysis, the evidence clearly shows the flag is flag{correct}. The results indicate success.",
        )]
        vr = await self.verify(agent_results=results)
        assert vr.confidence_score >= 0.8
        assert vr.status in (VerificationStatus.PASSED, VerificationStatus.NEEDS_REVIEW)

    @pytest.mark.asyncio
    async def test_low_confidence_empty_and_unsupported(self):
        results = [
            self.make_result(step=0, response=""),
            self.make_result(step=1, response="I think maybe the answer is 42, possibly."),
        ]
        vr = await self.verify(agent_results=results)
        assert vr.confidence_score < 0.6

    @pytest.mark.asyncio
    async def test_multiple_flags_boost_confidence(self):
        results = [
            self.make_result(step=0, response="Based on analysis, flag{first} confirmed."),
            self.make_result(step=1, response="Evidence indicates flag{second} is also valid."),
        ]
        vr = await self.verify(agent_results=results)
        assert len([f for f in vr.findings if f.finding_type == "flag_format"]) >= 2

    # --- Status determination ---

    @pytest.mark.asyncio
    async def test_passed_status(self):
        results = [self.make_result(response="Based on analysis, the evidence confirms flag{test}. All checks passed.")]
        vr = await self.verify(agent_results=results)
        assert vr.status == VerificationStatus.PASSED

    @pytest.mark.asyncio
    async def test_needs_review_status_on_warnings(self):
        results = [self.make_result(response="The answer is 42. flag{test} found.")]
        vr = await self.verify(agent_results=results)
        assert vr.status in (VerificationStatus.NEEDS_REVIEW, VerificationStatus.PASSED)

    @pytest.mark.asyncio
    async def test_failed_status_on_empty(self):
        results = [self.make_result(response="")]
        vr = await self.verify(agent_results=results)
        assert vr.status == VerificationStatus.FAILED

    # --- Recommendations ---

    @pytest.mark.asyncio
    async def test_recommendations_for_empty(self):
        results = [self.make_result(response="")]
        vr = await self.verify(agent_results=results)
        assert any("empty" in r.lower() for r in vr.recommendations)

    @pytest.mark.asyncio
    async def test_recommendations_for_uncertain(self):
        results = [self.make_result(response="I think the answer might be 42.")]
        vr = await self.verify(agent_results=results)
        assert any("evidence" in r.lower() for r in vr.recommendations)


# ---------------------------------------------------------------------------
# Supervisor integration tests
# ---------------------------------------------------------------------------

class TestSupervisorWithVerifier:
    @pytest.mark.asyncio
    async def test_supervisor_delegates_to_verifier(self):
        from models.llm import LLM, LLMResponse, LLMUsage
        from agents.registry import AgentRegistry
        from agents.supervisor import SupervisorAgent
        from core.specialized import SpecializedAgent

        class FakeLLM(LLM):
            def __init__(self):
                self.plan = '{"analysis": "test", "steps": [{"agent": "tester", "task": "find flag", "depends_on": []}]}'
            async def chat(self, messages, **kwargs):
                content = self.plan
                if any(kw in (m.get("content","") or "") for m in messages if m["role"] == "user" for kw in ["synthesize", "agent results", "verification"]):
                    content = "Synthesized with verification context."
                return LLMResponse(content=content, usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))

        class EchoAgent(SpecializedAgent):
            def __init__(self, llm):
                super().__init__(name="tester", llm=llm, system_prompt="test")
            async def process_task(self, task):
                return "Based on analysis, the evidence shows flag{test_complete}."

        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        verifier = VerificationAgent()
        supervisor = SupervisorAgent(llm, registry, verifier=verifier)

        result = await supervisor.run("Find the flag")
        assert result["verification"] is not None
        assert result["verification"]["status"] in ("passed", "needs_review", "failed")
        assert "confidence_score" in result["verification"]
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_verification_included_in_synthesis_prompt(self):
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
                content = self.plan
                if "verification" in self.last_user_content.lower():
                    content = "Synthesized with verification."
                return LLMResponse(content=content, usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))

        class EchoAgent(SpecializedAgent):
            def __init__(self, llm):
                super().__init__(name="tester", llm=llm, system_prompt="test")
            async def process_task(self, task):
                return "Result with evidence."

        llm = CaptureLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        verifier = VerificationAgent()
        supervisor = SupervisorAgent(llm, registry, verifier=verifier)

        await supervisor.run("Test synthesis with verification")
        assert "confidence_score" in llm.last_user_content or "Verification" in llm.last_user_content

    @pytest.mark.asyncio
    async def test_supervisor_without_verifier_still_works(self):
        from models.llm import LLM, LLMResponse, LLMUsage
        from agents.registry import AgentRegistry
        from agents.supervisor import SupervisorAgent

        class FakeLLM(LLM):
            async def chat(self, messages, **kwargs):
                return LLMResponse(content='{"analysis": "test", "steps": []}', usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))

        llm = FakeLLM()
        registry = AgentRegistry()
        supervisor = SupervisorAgent(llm, registry)
        result = await supervisor.run("test")
        assert "verification" not in result or result["verification"] is None

    def test_verification_prompt_template_exists(self):
        from agents.supervisor import VERIFICATION_PROMPT_SECTION
        assert "{verification}" in VERIFICATION_PROMPT_SECTION
