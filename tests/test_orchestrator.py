"""Tests for the orchestrator and end-to-end agent flow."""

import pytest
from core.memory import MemoryStore
from core.planner import TaskPlanner
from core.orchestrator import Orchestrator
from core.agent import BaseAgent, AgentContext, AgentResult
from models.llm import LLMResponse, LLMUsage


class FakeLLM:
    """A deterministic LLM stub that returns fixed responses."""

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        return LLMResponse(content="1. Execute the task\n2. Review the result")


class FakePlanner(TaskPlanner):
    """Planner stub that returns a fixed two-step plan."""

    async def create_plan(self, objective: str):
        from core.planner import PlanStep, TaskPlan
        return TaskPlan(objective=objective, steps=[
            PlanStep(1, "executor", f"Execute: {objective}", "done"),
            PlanStep(2, "reviewer", "Review results", "reviewed"),
        ])


class FakeAgent(BaseAgent):
    def __init__(self, name: str):
        super().__init__(name=name, llm=None, system_prompt="")

    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=f"{self.name} handled: {context.objective}",
        )


@pytest.mark.asyncio
async def test_orchestrator_runs_full_cycle():
    memory = MemoryStore()
    planner = FakePlanner(FakeLLM())
    orchestrator = Orchestrator(planner, memory)

    orchestrator.register_agent(FakeAgent("executor"))
    orchestrator.register_agent(FakeAgent("reviewer"))

    result = await orchestrator.run("task-1", "test objective")

    assert result["task_id"] == "task-1"
    assert result["objective"] == "test objective"
    assert len(result["plan"]) == 2
    assert "executor" in result["output"]
    assert "reviewer" in result["output"]


@pytest.mark.asyncio
async def test_orchestrator_missing_agent_returns_partial():
    memory = MemoryStore()
    planner = FakePlanner(FakeLLM())
    orchestrator = Orchestrator(planner, memory)

    # No agents registered — steps will have errors but plan still runs
    result = await orchestrator.run("task-2", "test")
    assert result["task_id"] == "task-2"
    assert len(result["plan"]) == 2
