"""
Specialized agent base class.

Purpose: Extends the abstract BaseAgent with built-in messaging support.
Every specialized agent (Coder, Security, QA, etc.) inherits from this
class, which provides a standard `receive` method that takes an
AgentMessage and returns an AgentMessage reply.

Clean architecture: Specialized agents depend on the LLM interface and
the protocol. They do not import each other or the Supervisor.
"""

import logging
from abc import abstractmethod
from typing import Optional

from models.llm import LLM, LLMResponse
from core.agent import BaseAgent, AgentContext, AgentResult
from core.protocol import AgentMessage

logger = logging.getLogger("agent.specialized")


class SpecializedAgent(BaseAgent):
    """
    Base class for all specialized agents with messaging support.
    Subclasses override `process_task()` to implement their logic.
    """

    def __init__(self, name: str, llm: LLM, system_prompt: str):
        super().__init__(name, llm, system_prompt)
        self.conversation_history: list[AgentMessage] = []

    # ------------------------------------------------------------------
    # Public API: receive a message, return a reply
    # ------------------------------------------------------------------

    async def receive(self, message: AgentMessage) -> AgentMessage:
        """
        Receive a message from another agent, process it, and return a reply.
        This is the primary entry point for inter-agent communication.
        """
        logger.info("%s received task from %s: %.60s", self.name, message.sender, message.task)

        self.conversation_history.append(message)

        try:
            response_text = await self.process_task(message.task)
            reply = message.reply(response_text, status="completed")
        except Exception as e:
            logger.exception("%s failed processing task: %s", self.name, e)
            reply = message.reply(str(e), status="failed")

        self.conversation_history.append(reply)
        return reply

    @abstractmethod
    async def process_task(self, task: str) -> str:
        """
        Process a task string and return a result string.
        Subclasses implement their domain-specific logic here.
        """
        ...

    # ------------------------------------------------------------------
    # BaseAgent compatibility (for the old orchestrator)
    # ------------------------------------------------------------------

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Legacy compatibility: wraps process_task in the old AgentContext pattern.
        """
        try:
            task = context.plan.get("step", context.objective) if context.plan else context.objective
            output = await self.process_task(task)
            return AgentResult(agent_name=self.name, success=True, output=output)
        except Exception as e:
            return AgentResult(agent_name=self.name, success=False, output="", error=str(e))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _llm_chat(self, messages: list[dict], **kwargs) -> str:
        """Shorthand for an LLM call that returns just the text."""
        response = await self.llm.chat(messages, **kwargs)
        return response.content

    def _build_messages(self, user_content: str) -> list[dict]:
        """Build a standard system+user message list."""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]
