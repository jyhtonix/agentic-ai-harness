"""Tests for the SkillPlanner and TaskPlan models."""

import json

import pytest
from pydantic import ValidationError

from models.llm import LLM, LLMResponse, LLMUsage
from agents.registry import AgentRegistry
from agents.supervisor import SupervisorAgent
from core.protocol import AgentMessage
from core.specialized import SpecializedAgent

from skills_engine.planner import PlanStep, TaskPlan, SkillPlanner
from skills_engine.registry import SkillRegistry
from skills_engine.selector import SkillSelector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeLLM(LLM):
    def __init__(self, plan_response=None):
        self.plan_response = plan_response or (
            '{"analysis": "Test analysis", '
            '"steps": [{"agent": "tester", "task": "do the thing", "depends_on": []}]}'
        )

    async def chat(self, messages, **kwargs):
        content = self.plan_response
        if any("synthesize" in m["content"].lower() or "agent results" in m["content"].lower()
               for m in messages if m["role"] == "user"):
            content = "Synthesized final response."
        return LLMResponse(
            content=content,
            usage=LLMUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )


class FakeSkillLLM(LLM):
    """LLM that verifies skill categories appear in the planning prompt."""

    def __init__(self):
        self.received_prompt = ""

    async def chat(self, messages, **kwargs):
        for m in messages:
            if m["role"] == "system":
                self.received_prompt = m["content"]
        return LLMResponse(
            content='{"analysis": "x", "steps": [{"agent": "tester", "task": "y", "depends_on": []}]}',
            usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


class EchoAgent(SpecializedAgent):
    def __init__(self, llm):
        super().__init__(name="tester", llm=llm, system_prompt="You are a test agent.")

    async def process_task(self, task: str) -> str:
        return f"Tester processed: {task}"


# ---------------------------------------------------------------------------
# PlanStep model tests
# ---------------------------------------------------------------------------

class TestPlanStep:
    def test_minimal(self):
        step = PlanStep(agent="coder", task="write code")
        assert step.agent == "coder"
        assert step.task == "write code"
        assert step.depends_on == []

    def test_with_dependencies(self):
        step = PlanStep(agent="researcher", task="research topic", depends_on=[0, 2])
        assert step.depends_on == [0, 2]

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            PlanStep(agent="coder")

    def test_serialize(self):
        step = PlanStep(agent="a", task="t", depends_on=[1])
        d = step.model_dump()
        assert d == {"agent": "a", "task": "t", "depends_on": [1]}


# ---------------------------------------------------------------------------
# TaskPlan model tests
# ---------------------------------------------------------------------------

class TestTaskPlan:
    def test_minimal(self):
        plan = TaskPlan(
            analysis="Test plan",
            steps=[PlanStep(agent="a", task="t")],
        )
        assert plan.analysis == "Test plan"
        assert len(plan.steps) == 1

    def test_empty_steps(self):
        plan = TaskPlan(analysis="Empty", steps=[])
        assert len(plan.steps) == 0

    def test_to_dict(self):
        plan = TaskPlan(
            analysis="Analyse this",
            steps=[PlanStep(agent="c", task="d", depends_on=[0])],
        )
        d = plan.to_dict()
        assert d["analysis"] == "Analyse this"
        assert d["steps"][0]["agent"] == "c"
        assert d["steps"][0]["task"] == "d"
        assert d["steps"][0]["depends_on"] == [0]

    def test_roundtrip_json(self):
        plan = TaskPlan(
            analysis="Roundtrip",
            steps=[PlanStep(agent="x", task="y")],
        )
        data = json.loads(json.dumps(plan.to_dict()))
        restored = TaskPlan(**data)
        assert restored.analysis == "Roundtrip"
        assert restored.steps[0].agent == "x"

    def test_model_dump_matches_supervisor_format(self):
        """TaskPlan.to_dict() must produce the same shape the Supervisor expects."""
        plan = TaskPlan(
            analysis="test",
            steps=[PlanStep(agent="a", task="t", depends_on=[])],
        )
        d = plan.to_dict()
        assert "analysis" in d
        assert "steps" in d
        assert isinstance(d["steps"], list)
        for step in d["steps"]:
            assert "agent" in step
            assert "task" in step
            assert "depends_on" in step


# ---------------------------------------------------------------------------
# SkillPlanner unit tests
# ---------------------------------------------------------------------------

class TestSkillPlanner:
    @pytest.mark.asyncio
    async def test_create_plan_valid_json(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        planner = SkillPlanner(llm, registry)
        plan = await planner.create_plan("Test request")
        assert isinstance(plan, TaskPlan)
        assert plan.analysis == "Test analysis"
        assert len(plan.steps) == 1
        assert plan.steps[0].agent == "tester"

    @pytest.mark.asyncio
    async def test_create_plan_invalid_json_fallback(self):
        llm = FakeLLM(plan_response="not valid json at all")
        registry = AgentRegistry()
        planner = SkillPlanner(llm, registry)
        plan = await planner.create_plan("Fallback test")
        assert isinstance(plan, TaskPlan)
        assert plan.analysis is not None

    @pytest.mark.asyncio
    async def test_create_plan_fallback_uses_registry(self):
        llm = FakeLLM(plan_response="{broken")
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        planner = SkillPlanner(llm, registry)
        plan = await planner.create_plan("Test")
        assert len(plan.steps) >= 1
        assert plan.steps[0].agent == "tester"

    @pytest.mark.asyncio
    async def test_create_plan_empty_registry(self):
        """Fallback with an empty registry should produce zero steps."""
        llm = FakeLLM(plan_response="{broken json")
        registry = AgentRegistry()
        planner = SkillPlanner(llm, registry)
        plan = await planner.create_plan("Empty test")
        assert len(plan.steps) == 0

    @pytest.mark.asyncio
    async def test_plan_to_dict(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        planner = SkillPlanner(llm, registry)
        plan = await planner.create_plan("Dict test")
        d = plan.to_dict()
        assert isinstance(d, dict)
        assert "analysis" in d
        assert "steps" in d

    @pytest.mark.asyncio
    async def test_prompt_includes_skill_categories(self):
        llm = FakeSkillLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))

        skill_registry = SkillRegistry()
        skill_registry.register({
            "frontmatter": {
                "name": "test-skill", "description": "A test skill.",
                "subdomain": "web", "category": "web", "tags": ["web"],
            },
            "metadata": {"path": "skills/test-skill"},
        })
        selector = SkillSelector(skill_registry)
        planner = SkillPlanner(llm, registry, skill_selector=selector)

        await planner.create_plan("Test with skills")

        assert "skill" in llm.received_prompt.lower()
        assert "test-skill" in llm.received_prompt or "web" in llm.received_prompt


# ---------------------------------------------------------------------------
# Supervisor delegation tests
# ---------------------------------------------------------------------------

class TestSupervisorWithPlanner:
    @pytest.mark.asyncio
    async def test_supervisor_delegates_to_planner(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))

        planner = SkillPlanner(llm, registry)
        supervisor = SupervisorAgent(llm, registry, planner=planner)

        result = await supervisor.run("Delegate test")
        assert result["request"] == "Delegate test"
        assert len(result["agent_results"]) >= 1

    @pytest.mark.asyncio
    async def test_supervisor_with_planner_plan_in_output(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        planner = SkillPlanner(llm, registry)
        supervisor = SupervisorAgent(llm, registry, planner=planner)

        result = await supervisor.run("Plan check")
        assert "plan" in result
        assert len(result["plan"]) >= 1

    @pytest.mark.asyncio
    async def test_supervisor_without_planner_still_works(self):
        """Existing behaviour: no planner → use legacy inline planning."""
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        supervisor = SupervisorAgent(llm, registry)

        result = await supervisor.run("No planner")
        assert result["request"] == "No planner"
        assert len(result["agent_results"]) >= 1

    @pytest.mark.asyncio
    async def test_supervisor_planner_fallback_on_bad_json(self):
        llm = FakeLLM(plan_response="corrupt")
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        planner = SkillPlanner(llm, registry)
        supervisor = SupervisorAgent(llm, registry, planner=planner)

        result = await supervisor.run("Bad JSON")
        assert len(result["agent_results"]) >= 1

    @pytest.mark.asyncio
    async def test_supervisor_conversation_history_with_planner(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        planner = SkillPlanner(llm, registry)
        supervisor = SupervisorAgent(llm, registry, planner=planner)

        await supervisor.run("History")
        assert len(supervisor.conversation_history) >= 2
