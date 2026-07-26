"""
Agent Registry.

Purpose: Central registry for all specialized agents. Maps agent names
to their implementations so the Supervisor can discover and dispatch
to agents by name without importing them directly.

Usage:
    registry = AgentRegistry()
    registry.register("researcher", ResearchAgent(llm))
    agent = registry.get("researcher")
    agents = registry.list_agents()
"""

import logging
from typing import Optional

from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.registry")


class AgentRegistry:
    """
    Registry mapping agent names to SpecializedAgent instances.
    Thread-safe in async context.
    """

    def __init__(self):
        self._agents: dict[str, SpecializedAgent] = {}

    def register(self, agent: SpecializedAgent) -> None:
        """Register an agent instance by its name."""
        self._agents[agent.name] = agent
        logger.info("Registered agent: %s", agent.name)

    def get(self, name: str) -> Optional[SpecializedAgent]:
        """Retrieve an agent by name. Returns None if not found."""
        return self._agents.get(name)

    def list_agents(self) -> dict[str, str]:
        """Return a dict of agent name → description."""
        return {
            name: agent.system_prompt.split(".")[0][:80]
            for name, agent in self._agents.items()
        }

    def remove(self, name: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(name, None)
        logger.info("Removed agent: %s", name)

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __len__(self) -> int:
        return len(self._agents)
