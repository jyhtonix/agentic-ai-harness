from __future__ import annotations

import json
import logging
from typing import Optional

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from models.llm import LLM
from agents.registry import AgentRegistry

logger = logging.getLogger("skills_engine.planner")


class PlanStep(BaseModel):
    agent: str
    task: str
    depends_on: list[int] = []


class TaskPlan(BaseModel):
    analysis: str
    steps: list[PlanStep]

    def to_dict(self) -> dict:
        return self.model_dump()


DISPATCH_SYSTEM_PROMPT = """You are a Supervisor Agent. You coordinate
specialized agents to complete complex user requests.

For each request:
1. Analyse what the user needs
2. Identify which specialized agents are required
3. Plan the order of operations (parallel vs sequential)
4. After receiving all results, synthesise a final response

Available agents: {agents}

Return a JSON plan with:
- analysis: your understanding of the request
- steps: array of objects with keys: agent, task, depends_on
- depends_on: list of step indices that must complete first"""


class SkillPlanner:
    def __init__(self, llm: LLM, registry: AgentRegistry, skill_selector=None):
        self.llm = llm
        self.registry = registry
        self.skill_selector = skill_selector

    async def create_plan(self, request: str) -> TaskPlan:
        agents_desc = json.dumps(self.registry.list_agents(), indent=2)
        skills_desc = ""
        if self.skill_selector:
            categories = (
                self.skill_selector.registry.get_categories()
                if hasattr(self.skill_selector, "registry")
                else {}
            )
            if categories:
                skills_desc = "\nAvailable skill categories:\n" + "\n".join(
                    f"  - {cat}: {count} skill(s)"
                    for cat, count in sorted(categories.items())
                )

        prompt = DISPATCH_SYSTEM_PROMPT.format(agents=agents_desc) + skills_desc

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Analyse this request and create a dispatch plan:\n\n{request}"
                ),
            },
        ]

        response = await self.llm.chat(messages, temperature=0.3)

        try:
            data = json.loads(response.content)
            return TaskPlan(**data)
        except (json.JSONDecodeError, TypeError, PydanticValidationError) as exc:
            logger.warning(
                "SkillPlanner plan was not valid: %s — using fallback", exc
            )
            return self._fallback_plan(request)

    def _fallback_plan(self, request: str) -> TaskPlan:
        agents = list(self.registry.list_agents().keys())
        steps = [
            PlanStep(agent=agent, task=request, depends_on=[])
            for agent in agents
        ]
        return TaskPlan(
            analysis=f"Analyse: {request}",
            steps=steps,
        )
