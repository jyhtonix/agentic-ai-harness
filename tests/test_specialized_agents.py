"""Tests for specialized agents using the messaging protocol."""

import pytest
from models.llm import LLM, LLMResponse, LLMUsage
from core.protocol import AgentMessage
from core.specialized import SpecializedAgent
from agents.researcher import ResearchAgent
from agents.coder import CodingAgent
from agents.security import SecurityAgent
from agents.qa import QAAgent


class FakeLLM(LLM):
    async def chat(self, messages, **kwargs):
        return LLMResponse(
            content=f"Processed: {messages[-1]['content'][:80]}",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


@pytest.mark.asyncio
async def test_researcher_receive_message():
    llm = FakeLLM()
    agent = ResearchAgent(llm)
    msg = AgentMessage(sender="supervisor", receiver="researcher", task="Research quantum computing")
    reply = await agent.receive(msg)
    assert reply.status == "completed"
    assert len(reply.response) > 0
    assert "Processed:" in reply.response


@pytest.mark.asyncio
async def test_coder_receive_message():
    llm = FakeLLM()
    agent = CodingAgent(llm)
    msg = AgentMessage(sender="supervisor", receiver="coder", task="Write a hello world function")
    reply = await agent.receive(msg)
    assert reply.status == "completed"
    assert len(reply.response) > 0


@pytest.mark.asyncio
async def test_security_receive_message():
    llm = FakeLLM()
    agent = SecurityAgent(llm)
    msg = AgentMessage(sender="supervisor", receiver="security", task="Review this code for SQL injection")
    reply = await agent.receive(msg)
    assert reply.status == "completed"


@pytest.mark.asyncio
async def test_qa_receive_message():
    llm = FakeLLM()
    agent = QAAgent(llm)
    msg = AgentMessage(sender="supervisor", receiver="qa", task="Verify this code is correct")
    reply = await agent.receive(msg)
    assert reply.status == "completed"


@pytest.mark.asyncio
async def test_conversation_history():
    llm = FakeLLM()
    agent = ResearchAgent(llm)
    msg = AgentMessage(sender="supervisor", receiver="researcher", task="Research topic")
    await agent.receive(msg)
    assert len(agent.conversation_history) == 2  # request + reply


@pytest.mark.asyncio
async def test_legacy_execute_compatibility():
    """Test that specialized agents still work with the old BaseAgent.execute()."""
    llm = FakeLLM()
    agent = ResearchAgent(llm)
    from core.agent import AgentContext
    ctx = AgentContext(task_id="1", objective="Research AI", plan={"step": "Research latest AI trends"})
    result = await agent.execute(ctx)
    assert result.success
    assert len(result.output) > 0
