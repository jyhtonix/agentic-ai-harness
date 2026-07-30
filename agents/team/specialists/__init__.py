import logging
from typing import Optional

from agents.team.evidence import AgentFinding
from agents.team.communication import TeamMessage, MessageType

logger = logging.getLogger("agents.team.specialists.base")


class SpecialistAgent:
    name: str = ""
    capabilities: list[str] = []
    category: str = ""

    def __init__(self, tool_executor=None, tool_selector=None, skill_selector=None):
        self.tool_executor = tool_executor
        self.tool_selector = tool_selector
        self.skill_selector = skill_selector

    async def analyze(self, task: str, context: Optional[dict] = None) -> AgentFinding:
        raise NotImplementedError

    async def receive_message(self, message: TeamMessage) -> TeamMessage:
        if message.type == MessageType.TASK:
            finding = await self.analyze(message.payload, message.metadata)
            return TeamMessage(
                type=MessageType.FINDING,
                sender=self.name,
                target=message.sender,
                payload=founding.findings[0] if founding.findings else "",
                evidence=founding.evidence,
                confidence=founding.confidence,
                task_id=message.task_id,
                status="completed",
            )
        return TeamMessage(
            type=MessageType.STATUS,
            sender=self.name,
            target=message.sender,
            payload=f"Unknown message type: {message.type}",
            task_id=message.task_id,
            status="failed",
        )

    def _build_context(self, task: str, context: Optional[dict] = None) -> str:
        parts = [task]
        if context:
            for k, v in context.items():
                parts.append(f"{k}: {v}")
        return "\n".join(parts)
