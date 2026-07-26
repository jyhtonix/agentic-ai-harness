"""
Reviewer agent.

Purpose: Evaluates the quality and completeness of a task result.
Scores the output, identifies gaps, and suggests improvements.
Acts as a quality gate before results are returned to the user.

Clean architecture: Extends BaseAgent. The reviewer is called
as the final step in the orchestrator's lifecycle. If the score
is low, the orchestrator could loop back to the planner for
re-execution.
"""

from core.agent import BaseAgent, AgentContext, AgentResult
from models.llm import LLM

REVIEWER_AGENT_PROMPT = """You are a reviewer. Evaluate the quality and completeness
of the task result. Score from 0.0 (failure) to 1.0 (perfect). Provide
reasoning and specific improvements if the score is below 0.8.

Respond with:
Score: <number>
Reasoning: <explanation>
Improvements: <list or 'None'>"""


class ReviewerAgent(BaseAgent):
    """Evaluates task results and provides quality scores."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="reviewer",
            llm=llm,
            system_prompt=REVIEWER_AGENT_PROMPT,
        )

    async def execute(self, context: AgentContext) -> AgentResult:
        """Review the accumulated results and assign a quality score."""
        try:
            combined = "\n".join(context.previous_results) if context.previous_results else "No results to review."
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Objective: {context.objective}\n\nResults:\n{combined}"},
            ]
            response = await self.llm.chat(messages, temperature=0.3)
            return AgentResult(agent_name=self.name, success=True, output=response.content)
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, output="", error=str(e))
