"""
Task planner.

Purpose: Breaks a high-level user objective into a sequence of concrete,
executable steps. Each step specifies which agent should handle it and
what action to take.

Clean architecture: The planner is a service — the orchestrator passes
in the objective and gets back a structured plan. It delegates to the
LLM for the reasoning but owns the Plan dataclass.
"""

from dataclasses import dataclass, field
from typing import Optional

from models.llm import LLM


@dataclass
class PlanStep:
    """A single step in a task execution plan."""
    step_number: int
    agent: str          # "planner" | "executor" | "researcher" | "reviewer"
    action: str         # what the agent should do
    expected_outcome: str
    dependencies: list[int] = field(default_factory=list)


@dataclass
class TaskPlan:
    """Complete decomposition of a task into ordered steps."""
    objective: str
    steps: list[PlanStep]


PLANNER_SYSTEM_PROMPT = """You are a planner that breaks user requests into steps.
For each step specify: step number, agent (planner/executor/researcher/reviewer),
action description, expected outcome, and dependencies (list of step numbers
that must finish first).

Return the plan as a numbered list."""


class TaskPlanner:
    """
    Decomposes a user objective into a structured plan using an LLM.
    Keeps planning logic separate from agent execution logic.
    """

    def __init__(self, llm: LLM):
        self.llm = llm

    async def create_plan(self, objective: str) -> TaskPlan:
        """Generate a step-by-step plan for the given objective."""
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Objective: {objective}\n\nCreate a detailed plan."},
        ]
        response = await self.llm.chat(messages, temperature=0.3)
        steps = self._parse_steps(response.content)
        return TaskPlan(objective=objective, steps=steps or [self._default_step(objective)])

    def _parse_steps(self, text: str) -> list[PlanStep]:
        """Parse LLM output into a list of PlanStep objects."""
        steps = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or not line[0].isdigit():
                continue
            steps.append(PlanStep(
                step_number=len(steps) + 1,
                agent="executor",
                action=line,
                expected_outcome="Completed",
            ))
        return steps

    def _default_step(self, objective: str) -> PlanStep:
        """Fallback single-step plan when parsing fails."""
        return PlanStep(
            step_number=1,
            agent="executor",
            action=objective,
            expected_outcome="Completed",
        )
