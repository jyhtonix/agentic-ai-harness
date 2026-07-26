"""Tests for the Agent Registry."""

import pytest
from agents.registry import AgentRegistry


class FakeAgent:
    def __init__(self, name: str):
        self.name = name
        self.system_prompt = "I am a test agent."


class TestAgentRegistry:
    def test_register_and_get(self):
        r = AgentRegistry()
        agent = FakeAgent("tester")
        r.register(agent)
        assert r.get("tester") is agent

    def test_get_missing(self):
        r = AgentRegistry()
        assert r.get("nonexistent") is None

    def test_list_agents(self):
        r = AgentRegistry()
        r.register(FakeAgent("agent_a"))
        r.register(FakeAgent("agent_b"))
        agents = r.list_agents()
        assert "agent_a" in agents
        assert "agent_b" in agents

    def test_remove(self):
        r = AgentRegistry()
        r.register(FakeAgent("temp"))
        r.remove("temp")
        assert r.get("temp") is None

    def test_contains(self):
        r = AgentRegistry()
        r.register(FakeAgent("present"))
        assert "present" in r
        assert "absent" not in r

    def test_len(self):
        r = AgentRegistry()
        assert len(r) == 0
        r.register(FakeAgent("a"))
        assert len(r) == 1
