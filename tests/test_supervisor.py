"""Tests for the Supervisor Agent and end-to-end multi-agent workflow."""

import pytest
from models.llm import LLM, LLMResponse, LLMUsage
from core.protocol import AgentMessage
from core.specialized import SpecializedAgent
from agents.registry import AgentRegistry
from agents.supervisor import SupervisorAgent


class FakeLLM(LLM):
    def __init__(self):
        self.plan_response = '{"analysis": "User needs help", "steps": [{"agent": "tester", "task": "do the thing", "depends_on": []}]}'

    async def chat(self, messages, **kwargs):
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        content = self.plan_response
        # If this is a synthesis call, return a different response
        if "synthesize" in user.lower() or "agent results" in user.lower():
            content = "Synthesized final response."
        return LLMResponse(
            content=content,
            usage=LLMUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )


class EchoAgent(SpecializedAgent):
    """Simple test agent that echoes the task."""

    def __init__(self, llm):
        super().__init__(name="tester", llm=llm, system_prompt="You are a test agent.")

    async def process_task(self, task: str) -> str:
        return f"Tester processed: {task}"


@pytest.mark.asyncio
async def test_supervisor_dispatch_to_single_agent():
    llm = FakeLLM()
    registry = AgentRegistry()
    registry.register(EchoAgent(llm))
    supervisor = SupervisorAgent(llm, registry)

    result = await supervisor.run("Test the system")
    assert result["request"] == "Test the system"
    assert len(result["agent_results"]) >= 1
    assert result["final_response"] != ""


@pytest.mark.asyncio
async def test_supervisor_missing_agent_handled_gracefully():
    """If an agent is not in the registry, the supervisor should log and continue."""
    llm = FakeLLM()
    llm.plan_response = '{"analysis": "test", "steps": [{"agent": "nonexistent", "task": "doit", "depends_on": []}]}'
    registry = AgentRegistry()
    supervisor = SupervisorAgent(llm, registry)

    result = await supervisor.run("Test missing agent")
    assert len(result["agent_results"]) >= 1
    assert "not found" in result["agent_results"][0]["response"]


@pytest.mark.asyncio
async def test_supervisor_respects_dependencies():
    """Steps should execute in dependency order."""
    llm = FakeLLM()
    llm.plan_response = '{"analysis": "multi-step", "steps": [{"agent": "tester", "task": "first", "depends_on": []}, {"agent": "tester", "task": "second", "depends_on": [0]}]}'
    registry = AgentRegistry()
    registry.register(EchoAgent(llm))
    supervisor = SupervisorAgent(llm, registry)

    result = await supervisor.run("Multi-step test")
    assert len(result["agent_results"]) == 2
    assert result["agent_results"][0]["step"] == 0
    assert result["agent_results"][1]["step"] == 1


@pytest.mark.asyncio
async def test_supervisor_fallback_plan():
    """When LLM output is not valid JSON, fallback should still work."""
    llm = FakeLLM()
    llm.plan_response = "not valid json at all"
    registry = AgentRegistry()
    registry.register(EchoAgent(llm))
    supervisor = SupervisorAgent(llm, registry)

    result = await supervisor.run("Fallback test")
    assert len(result["agent_results"]) >= 1  # fallback dispatches to all agents


@pytest.mark.asyncio
async def test_conversation_history_recorded():
    llm = FakeLLM()
    registry = AgentRegistry()
    registry.register(EchoAgent(llm))
    supervisor = SupervisorAgent(llm, registry)

    await supervisor.run("History test")
    assert len(supervisor.conversation_history) >= 2  # at least one request + reply pair
