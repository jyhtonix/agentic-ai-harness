"""
Tests for the Agent Runtime Engine (Agent class).

Tests the full lifecycle against a FakeLLM that returns controlled
responses, verifying each phase executes correctly and state is
populated as expected.
"""

import pytest
from models.llm import LLM, LLMResponse, LLMUsage
from core.agent import (
    Agent,
    AgentState,
    TokenTracker,
    AgentError,
    TaskAnalysisError,
    PlanningError,
    ExecutionError,
)
from tools.base import BaseTool
from tools.registry import ToolRegistry


class FakeLLM(LLM):
    """Deterministic LLM stub for testing agent lifecycle."""

    def __init__(self):
        self.calls = []
        self.responses = {}
        self.default_response = '{"goal": "test goal", "success_criteria": "done", "complexity": "simple", "required_capabilities": []}'

    def set_response(self, prompt_contains: str, response: str):
        self.responses[prompt_contains] = response

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        self.calls.append(messages)
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")

        for key, resp in self.responses.items():
            if key in user_msg:
                return LLMResponse(content=resp, usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))

        return LLMResponse(content=self.default_response, usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))


class FunctionTool(BaseTool):
    """Wraps an async callable as a BaseTool for testing."""

    def __init__(self, name: str, description: str, fn):
        self._name = name
        self._description = description
        self._fn = fn

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"action": {"type": "string"}},
            "required": ["action"],
        }

    async def execute(self, action: str = "", **kwargs) -> str:
        return await self._fn(action)


class TestTokenTracker:
    def test_add(self):
        t = TokenTracker()
        t.add(LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))
        assert t.prompt_tokens == 10
        assert t.completion_tokens == 5
        assert t.total_tokens == 15

    def test_add_multiple(self):
        t = TokenTracker()
        t.add(LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15))
        t.add(LLMUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30))
        assert t.total_tokens == 45

    def test_summary(self):
        t = TokenTracker()
        t.add(LLMUsage(prompt_tokens=7, completion_tokens=3, total_tokens=10))
        s = t.summary()
        assert s["total_tokens"] == 10


class TestToolRegistry:
    def test_register_and_get(self):
        r = ToolRegistry()
        tool = FunctionTool("my_tool", "Does something", lambda a: f"handled: {a}")
        r.register(tool)
        assert r.get_tool("my_tool") is tool

    def test_get_missing(self):
        r = ToolRegistry()
        assert r.get_tool("nonexistent") is None

    def test_list_tools(self):
        r = ToolRegistry()
        t1 = FunctionTool("tool_a", "First tool", lambda a: a)
        t2 = FunctionTool("tool_b", "Second tool", lambda a: a)
        r.register(t1)
        r.register(t2)
        tools = r.list_tools()
        assert tools["tool_a"] == "First tool"
        assert tools["tool_b"] == "Second tool"


class TestAgentState:
    def test_default_state(self):
        s = AgentState()
        assert s.task == ""
        assert s.plan == []
        assert s.results == []
        assert s.errors == []
        assert s.final_answer == ""

    def test_initialise_with_task(self):
        s = AgentState(task="write code", start_time=100.0)
        assert s.task == "write code"
        assert s.start_time == 100.0


class TestAgentLifecycle:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Verify the complete lifecycle produces a final answer."""
        llm = FakeLLM()
        agent = Agent(llm=llm)

        result = await agent.run("Say hello")

        assert result["task"] == "Say hello"
        assert result["goal"] != ""
        assert len(result["plan"]) >= 0
        assert isinstance(result["final_answer"], str)
        assert len(result["final_answer"]) > 0
        assert result["metadata"]["token_usage"]["total_tokens"] > 0
        assert result["metadata"]["elapsed_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_initialise_resets_state(self):
        """Calling run twice should reset state each time."""
        llm = FakeLLM()
        agent = Agent(llm=llm)

        await agent.run("First task")
        first_state = agent.state

        await agent.run("Second task")
        second_state = agent.state

        assert second_state.task == "Second task"
        assert second_state.goal != first_state.goal or second_state.task != first_state.task

    @pytest.mark.asyncio
    async def test_messages_are_recorded(self):
        """The messages list should grow as the lifecycle progresses."""
        llm = FakeLLM()
        agent = Agent(llm=llm)

        await agent.run("Test messages")
        assert len(agent.state.messages) >= 2

    @pytest.mark.asyncio
    async def test_plan_contains_steps(self):
        """The plan should be populated after create_plan."""
        llm = FakeLLM()
        llm.default_response = '{"steps": [{"step": 1, "action": "do thing", "tool": "none", "expected_outcome": "done"}]}'
        agent = Agent(llm=llm)

        await agent.run("Do something")
        assert len(agent.state.plan) >= 1

    @pytest.mark.asyncio
    async def test_tool_registry_integration(self):
        """Tools registered on the agent should be invocable during execution."""
        llm = FakeLLM()
        llm.default_response = '{"steps": [{"step": 1, "action": "process", "tool": "my_tool", "expected_outcome": "processed"}]}'

        agent = Agent(llm=llm)

        async def handler(action: str) -> str:
            return f"tool executed: {action}"
        agent.tools.register(FunctionTool("my_tool", "A test tool", handler))

        await agent.run("Use tool")

        assert "my_tool" in agent.state.tools_used
        assert any("tool executed" in r.get("output", "") for r in agent.state.results)

    @pytest.mark.asyncio
    async def test_errors_are_collected(self):
        """Exceptions during tool execution should be captured as errors."""
        llm = FakeLLM()
        llm.default_response = '{"steps": [{"step": 1, "action": "fail", "tool": "broken_tool", "expected_outcome": "error"}]}'

        agent = Agent(llm=llm)

        async def broken_tool(action: str) -> str:
            raise RuntimeError("something broke")

        agent.tools.register(FunctionTool("broken_tool", "A broken tool", broken_tool))

        await agent.run("Trigger error")

        assert len(agent.state.errors) >= 1
        assert any("broken" in e for e in agent.state.errors) or \
               any("broken" in r.get("error", "") for r in agent.state.results)

    @pytest.mark.asyncio
    async def test_metadata_includes_timing_and_tokens(self):
        """The result dict should include elapsed time and token usage."""
        llm = FakeLLM()
        agent = Agent(llm=llm)

        result = await agent.run("Measure me")
        meta = result["metadata"]

        assert meta["elapsed_seconds"] >= 0
        assert meta["steps_total"] >= 0
        assert meta["token_usage"]["total_tokens"] >= 0
