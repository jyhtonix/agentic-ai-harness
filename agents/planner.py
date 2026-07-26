"""
Planner agent.

Purpose: Refines or adjusts the initial plan during execution.
If the executor reports a failure, the planner can re-plan the
remaining steps. This agent exists so the orchestrator can call
it like any other agent through the same interface.

Clean architecture: Extends BaseAgent. The orchestrator routes
to it by name without caring what it does internally.
"""

from core.agent import BaseAgent, AgentContext, AgentResult
from models.llm import LLM

PLANNER_AGENT_PROMPT = """You are a planning agent. Given a task objective and
the results of previous steps, determine the next actions. If the plan is
complete, respond with "PLAN COMPLETE". Otherwise, describe the next step."""


class PlannerAgent(BaseAgent):
    """Analyses results and determines next steps or plan adjustments."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="planner",
            llm=llm,
            system_prompt=PLANNER_AGENT_PROMPT,
        )

    async def execute(self, context: AgentContext) -> AgentResult:
        """Review previous results and decide what to do next."""
        try:
            history = "\n".join(context.previous_results[-5:]) if context.previous_results else "No previous results."
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Objective: {context.objective}\n\nResults so far:\n{history}"},
            ]
            response = await self.llm.chat(messages, temperature=0.3)
            return AgentResult(agent_name=self.name, success=True, output=response.content)
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, output="", error=str(e))
