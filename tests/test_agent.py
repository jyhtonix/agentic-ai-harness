"""Tests for the base agent class."""

import pytest
from core.agent import BaseAgent, AgentContext, AgentResult


class DummyAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=f"Handled: {context.objective}",
        )


class TestBaseAgent:
    def test_agent_has_name(self):
        agent = DummyAgent(name="test", llm=None, system_prompt="test")
        assert agent.name == "test"

    @pytest.mark.asyncio
    async def test_agent_execute_returns_result(self):
        agent = DummyAgent(name="test", llm=None, system_prompt="test")
        ctx = AgentContext(task_id="1", objective="do something")
        result = await agent.execute(ctx)
        assert result.success
        assert "do something" in result.output
