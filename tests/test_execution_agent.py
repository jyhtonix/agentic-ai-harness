"""Tests for the ExecutionAgent, StepResult, and ExecutionResult models."""

import pytest
from pydantic import ValidationError

from models.llm import LLM, LLMResponse, LLMUsage
from agents.registry import AgentRegistry
from agents.supervisor import SupervisorAgent
from core.protocol import AgentMessage
from core.specialized import SpecializedAgent

from skills_engine.planner import PlanStep, TaskPlan
from skills_engine.execution import (
    ExecutionAgent,
    ExecutionResult,
    ExecutionStatus,
    StepResult,
)


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


class EchoAgent(SpecializedAgent):
    def __init__(self, llm):
        super().__init__(name="tester", llm=llm, system_prompt="You are a test agent.")

    async def process_task(self, task: str) -> str:
        return f"Tester processed: {task}"


class FailAgent(SpecializedAgent):
    def __init__(self, llm):
        super().__init__(name="failer", llm=llm, system_prompt="I always fail.")

    async def process_task(self, task: str) -> str:
        raise RuntimeError("Intentional failure for testing")


class SlowAgent(SpecializedAgent):
    def __init__(self, llm, fail_count=1):
        super().__init__(name="slow", llm=llm, system_prompt="I fail then succeed.")
        self.fail_count = fail_count
        self.call_count = 0

    async def process_task(self, task: str) -> str:
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise RuntimeError(f"Simulated failure {self.call_count}")
        return f"Slow processed after {self.call_count} attempt(s): {task}"


# ---------------------------------------------------------------------------
# StepResult model tests
# ---------------------------------------------------------------------------

class TestStepResult:
    def test_minimal(self):
        sr = StepResult(
            step_index=0,
            agent_name="coder",
            task="write tests",
            status=ExecutionStatus.COMPLETED,
        )
        assert sr.step_index == 0
        assert sr.agent_name == "coder"
        assert sr.status == ExecutionStatus.COMPLETED
        assert sr.response == ""
        assert sr.error is None
        assert sr.attempts == 1

    def test_full(self):
        sr = StepResult(
            step_index=1,
            agent_name="researcher",
            task="find sources",
            status=ExecutionStatus.FAILED,
            response="Error occurred",
            error="Agent not available",
            attempts=2,
        )
        assert sr.step_index == 1
        assert sr.status == ExecutionStatus.FAILED
        assert sr.attempts == 2

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            StepResult(step_index=0)

    def test_serialize(self):
        sr = StepResult(
            step_index=0,
            agent_name="a",
            task="t",
            status=ExecutionStatus.COMPLETED,
            response="ok",
        )
        d = sr.model_dump()
        assert d["step_index"] == 0
        assert d["status"] == "completed"
        assert d["response"] == "ok"


# ---------------------------------------------------------------------------
# ExecutionResult model tests
# ---------------------------------------------------------------------------

class TestExecutionResult:
    def test_minimal(self):
        er = ExecutionResult(
            plan_analysis="Test plan",
            step_results=[],
            overall_status=ExecutionStatus.COMPLETED,
        )
        assert er.plan_analysis == "Test plan"
        assert er.all_completed()

    def test_not_all_completed(self):
        er = ExecutionResult(
            plan_analysis="Partial",
            step_results=[
                StepResult(step_index=0, agent_name="a", task="t", status=ExecutionStatus.COMPLETED),
                StepResult(step_index=1, agent_name="b", task="u", status=ExecutionStatus.FAILED),
            ],
            overall_status=ExecutionStatus.FAILED,
        )
        assert not er.all_completed()

    def test_to_legacy_dicts(self):
        er = ExecutionResult(
            plan_analysis="Test",
            step_results=[
                StepResult(step_index=0, agent_name="a", task="t", status=ExecutionStatus.COMPLETED, response="ok"),
                StepResult(step_index=1, agent_name="b", task="u", status=ExecutionStatus.FAILED, response="bad", error="err"),
            ],
            overall_status=ExecutionStatus.FAILED,
        )
        legacy = er.to_legacy_dicts()
        assert len(legacy) == 2
        assert legacy[0]["agent"] == "a"
        assert legacy[0]["status"] == "completed"
        assert legacy[0]["step"] == 0
        assert legacy[1]["status"] == "failed"
        assert legacy[1]["error"] == "err"


# ---------------------------------------------------------------------------
# ExecutionAgent unit tests
# ---------------------------------------------------------------------------

class TestExecutionAgent:
    @pytest.mark.asyncio
    async def test_execute_single_step(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        agent = ExecutionAgent(registry)

        plan = TaskPlan(
            analysis="Test single step",
            steps=[PlanStep(agent="tester", task="do it")],
        )
        result = await agent.execute(plan, request="Single step test")
        assert result.overall_status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 1
        assert result.step_results[0].status == ExecutionStatus.COMPLETED
        assert "Tester processed: do it" in result.step_results[0].response

    @pytest.mark.asyncio
    async def test_execute_multiple_steps_sequential(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        agent = ExecutionAgent(registry)

        plan = TaskPlan(
            analysis="Multi-step",
            steps=[
                PlanStep(agent="tester", task="step one"),
                PlanStep(agent="tester", task="step two", depends_on=[0]),
            ],
        )
        result = await agent.execute(plan, request="Multi-step test")
        assert result.overall_status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 2
        assert result.step_results[0].status == ExecutionStatus.COMPLETED
        assert result.step_results[1].status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_parallel_steps(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        agent = ExecutionAgent(registry)

        plan = TaskPlan(
            analysis="Parallel",
            steps=[
                PlanStep(agent="tester", task="first"),
                PlanStep(agent="tester", task="second"),
                PlanStep(agent="tester", task="third"),
            ],
        )
        result = await agent.execute(plan, request="Parallel test")
        assert result.overall_status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 3

    @pytest.mark.asyncio
    async def test_execute_agent_not_found(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        agent = ExecutionAgent(registry)

        plan = TaskPlan(
            analysis="Missing agent",
            steps=[PlanStep(agent="nonexistent", task="do it")],
        )
        result = await agent.execute(plan, request="Missing agent test")
        assert result.overall_status == ExecutionStatus.FAILED
        assert len(result.step_results) == 1
        assert result.step_results[0].status == ExecutionStatus.FAILED
        assert "not found" in (result.step_results[0].error or "")

    @pytest.mark.asyncio
    async def test_step_failure_recorded(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(FailAgent(llm))
        agent = ExecutionAgent(registry)

        plan = TaskPlan(
            analysis="Failure test",
            steps=[PlanStep(agent="failer", task="will fail")],
        )
        result = await agent.execute(plan, request="Failure test")
        assert result.overall_status == ExecutionStatus.FAILED
        assert result.step_results[0].status == ExecutionStatus.FAILED
        assert not result.all_completed()

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(SlowAgent(llm, fail_count=1))
        agent = ExecutionAgent(registry, max_retries=3)

        plan = TaskPlan(
            analysis="Retry",
            steps=[PlanStep(agent="slow", task="will retry")],
        )
        result = await agent.execute(plan, request="Retry test")
        assert result.overall_status == ExecutionStatus.COMPLETED
        assert result.step_results[0].status == ExecutionStatus.COMPLETED
        assert result.step_results[0].attempts == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(FailAgent(llm))
        agent = ExecutionAgent(registry, max_retries=2)

        plan = TaskPlan(
            analysis="Exhaust retries",
            steps=[PlanStep(agent="failer", task="always fails")],
        )
        result = await agent.execute(plan, request="Exhaust retry test")
        assert result.overall_status == ExecutionStatus.FAILED
        assert result.step_results[0].attempts == 2

    @pytest.mark.asyncio
    async def test_deadlock_skipped_steps(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        agent = ExecutionAgent(registry)

        plan = TaskPlan(
            analysis="Deadlock",
            steps=[
                PlanStep(agent="tester", task="step b", depends_on=[1]),
                # step 0 depends on step 1, step 1 depends on step 0 → deadlock
                PlanStep(agent="tester", task="step a", depends_on=[0]),
            ],
        )
        result = await agent.execute(plan, request="Deadlock test")
        assert result.overall_status == ExecutionStatus.FAILED
        statuses = {r.step_index: r.status for r in result.step_results}
        assert any(s == ExecutionStatus.SKIPPED for s in statuses.values())

    @pytest.mark.asyncio
    async def test_empty_plan(self):
        registry = AgentRegistry()
        agent = ExecutionAgent(registry)
        plan = TaskPlan(analysis="Empty", steps=[])
        result = await agent.execute(plan, request="Empty test")
        assert result.overall_status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 0
        assert result.all_completed()

    @pytest.mark.asyncio
    async def test_to_legacy_dicts_via_execution(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        agent = ExecutionAgent(registry)

        plan = TaskPlan(
            analysis="Legacy test",
            steps=[PlanStep(agent="tester", task="convert")],
        )
        result = await agent.execute(plan, request="Legacy test")
        legacy = result.to_legacy_dicts()
        assert isinstance(legacy, list)
        assert len(legacy) == 1
        assert legacy[0]["agent"] == "tester"
        assert legacy[0]["status"] == "completed"
        assert legacy[0]["step"] == 0


# ---------------------------------------------------------------------------
# Supervisor delegation tests (with ExecutionAgent)
# ---------------------------------------------------------------------------

class TestSupervisorWithExecutionAgent:
    @pytest.mark.asyncio
    async def test_supervisor_delegates_to_execution_agent(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        execution_agent = ExecutionAgent(registry)
        supervisor = SupervisorAgent(
            llm, registry, execution_agent=execution_agent,
        )

        result = await supervisor.run("Delegate execution")
        assert result["request"] == "Delegate execution"
        assert len(result["agent_results"]) >= 1
        assert "Tester processed" in result["agent_results"][0]["response"]

    @pytest.mark.asyncio
    async def test_execution_with_planner_and_execution_agent(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        from skills_engine.planner import SkillPlanner
        planner = SkillPlanner(llm, registry)
        execution_agent = ExecutionAgent(registry)
        supervisor = SupervisorAgent(
            llm, registry, planner=planner, execution_agent=execution_agent,
        )

        result = await supervisor.run("Full pipeline")
        assert result["request"] == "Full pipeline"
        assert len(result["agent_results"]) >= 1

    @pytest.mark.asyncio
    async def test_conversation_history_with_execution_agent(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        execution_agent = ExecutionAgent(registry)
        supervisor = SupervisorAgent(
            llm, registry, execution_agent=execution_agent,
        )

        await supervisor.run("History test")
        assert len(supervisor.conversation_history) >= 2

    @pytest.mark.asyncio
    async def test_execution_agent_error_handling(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(FailAgent(llm))
        execution_agent = ExecutionAgent(registry)
        supervisor = SupervisorAgent(
            llm, registry, execution_agent=execution_agent,
        )

        result = await supervisor.run("Error test")
        assert len(result["agent_results"]) >= 1
        assert result["agent_results"][0]["status"] in ("failed", "completed")
        # Supervisor should still produce a final response even with failures
        assert result["final_response"] != ""

    @pytest.mark.asyncio
    async def test_supervisor_fallback_plan_with_execution_agent(self):
        llm = FakeLLM()
        llm.plan_response = "not valid json"
        registry = AgentRegistry()
        registry.register(EchoAgent(llm))
        execution_agent = ExecutionAgent(registry)
        supervisor = SupervisorAgent(
            llm, registry, execution_agent=execution_agent,
        )

        result = await supervisor.run("Fallback with exec")
        assert len(result["agent_results"]) >= 1

    @pytest.mark.asyncio
    async def test_missing_agent_with_execution_agent(self):
        llm = FakeLLM()
        llm.plan_response = '{"analysis": "test", "steps": [{"agent": "ghost", "task": "doit", "depends_on": []}]}'
        registry = AgentRegistry()
        execution_agent = ExecutionAgent(registry)
        supervisor = SupervisorAgent(
            llm, registry, execution_agent=execution_agent,
        )

        result = await supervisor.run("Missing agent with exec")
        assert len(result["agent_results"]) >= 1
        assert "not found" in result["agent_results"][0]["response"]
