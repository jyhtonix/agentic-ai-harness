"""
Executor agent.

Purpose: Carries out the actions specified in a plan step.
This is the primary "worker" agent — it interacts with tools
to perform tasks like reading files, making web requests, or
calling APIs. In the current version it uses the LLM to reason
about what to do; in future versions it will call tools directly.

Clean architecture: Extends BaseAgent. The executor's job is to
produce results from actions. What those actions are depends on
the step the orchestrator sends.
"""

from core.agent import BaseAgent, AgentContext, AgentResult
from models.llm import LLM

EXECUTOR_AGENT_PROMPT = """You are an executor agent. Your job is to carry out
the assigned action using available tools and report the result clearly.
If the action cannot be completed, explain why."""


class ExecutorAgent(BaseAgent):
    """Executes plan steps by reasoning with the LLM."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="executor",
            llm=llm,
            system_prompt=EXECUTOR_AGENT_PROMPT,
        )

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute a single action from the plan."""
        try:
            action = context.plan.get("step", "No action specified.") if context.plan else "No action specified."
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Objective: {context.objective}\n\nAction to execute:\n{action}"},
            ]
            response = await self.llm.chat(messages, temperature=0.3)
            return AgentResult(agent_name=self.name, success=True, output=response.content)
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, output="", error=str(e))
