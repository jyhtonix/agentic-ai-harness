"""
Central orchestrator.

Purpose: The main coordination engine. It receives a user objective,
delegates to the planner for decomposition, routes each step to the
appropriate agent, collects results, and returns the final output.

Lifeycle:
  1. Understand — (future: explicit task understanding step)
  2. Plan      — TaskPlanner decomposes the objective
  3. Execute   — Steps are dispatched to agents in dependency order
  4. Review    — Reviewer agent scores the final result
  5. Return    — Combined output is sent back to the caller

Clean architecture: Orchestrator depends on abstractions (BaseAgent, LLM,
TaskPlanner, MemoryStore). It does not import from tools/, api/, or any
concrete agent implementation — those are injected at startup.
"""

from typing import Optional

from core.agent import BaseAgent, AgentContext, AgentResult
from core.memory import MemoryStore
from core.planner import TaskPlanner, PlanStep


class Orchestrator:
    """
    Coordinates the full agent lifecycle for a single task.
    Stateless by design — all state lives in MemoryStore.
    """

    def __init__(self, planner: TaskPlanner, memory: MemoryStore):
        self.planner = planner
        self.memory = memory
        self._agents: dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a named agent so the orchestrator can route steps to it."""
        self._agents[agent.name] = agent

    async def run(self, task_id: str, objective: str) -> dict:
        """
        Execute the full agent lifecycle for an objective.
        Returns a dict with plan, step results, and final output.
        """
        # Phase 1: Store the initial request
        self.memory.save(task_id, {"objective": objective, "results": []})

        # Phase 2: Plan
        plan = await self.planner.create_plan(objective)
        self.memory.save(f"{task_id}:plan", {"steps": [str(s.action) for s in plan.steps]})

        # Phase 3: Execute steps in order
        completed: set[int] = set()
        results = []

        while len(completed) < len(plan.steps):
            for step in plan.steps:
                if step.step_number in completed:
                    continue
                if not all(dep in completed for dep in step.dependencies):
                    continue

                result = await self._run_step(task_id, step)
                results.append(result)
                completed.add(step.step_number)

        # Phase 4: Build final output
        output_parts = [r.output for r in results if r.success]
        final_output = "\n".join(output_parts)
        self.memory.save(task_id, {"objective": objective, "results": results, "output": final_output})

        return {
            "task_id": task_id,
            "objective": objective,
            "plan": [str(s.action) for s in plan.steps],
            "output": final_output,
        }

    async def _run_step(self, task_id: str, step: PlanStep) -> AgentResult:
        """Route a single plan step to the right agent and execute it."""
        agent = self._agents.get(step.agent)
        if not agent:
            return AgentResult(
                agent_name=step.agent,
                success=False,
                output="",
                error=f"No agent registered with name '{step.agent}'",
            )

        context = AgentContext(
            task_id=task_id,
            objective=self.memory.get(task_id).get("objective", ""),
            plan={"step": step.action},
            previous_results=self.memory.get(task_id).get("results", []),
        )

        result = await agent.execute(context)

        self.memory.append(task_id, "results", result.output)
        return result
