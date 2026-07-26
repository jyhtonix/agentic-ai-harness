"""
Agent communication protocol.

Purpose: Defines the standard message format for all inter-agent
communication. Every message between agents follows this schema,
enabling consistent logging, routing, and auditing.

Clean architecture: This is a pure data layer with no dependencies.
Both the Supervisor and all specialized agents depend on this protocol.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class AgentMessage:
    """
    Universal message format for agent-to-agent communication.

    Fields:
        sender:      Name of the sending agent (e.g. "supervisor", "researcher")
        receiver:    Name of the receiving agent (e.g. "coder", "security")
        task:        The task or instruction being sent
        response:    The response payload (populated on reply)
        status:      One of "pending", "in_progress", "completed", "failed"
        timestamp:   ISO-8601 timestamp of when the message was created
        conversation_id:  Optional ID linking related messages in a workflow
        metadata:    Optional dict for extra context (token_usage, errors, etc.)
    """
    sender: str
    receiver: str
    task: str = ""
    response: str = ""
    status: str = "pending"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    conversation_id: str = ""
    metadata: Optional[dict] = None

    def reply(self, response: str, status: str = "completed") -> "AgentMessage":
        """Create a reply message (swaps sender/receiver)."""
        return AgentMessage(
            sender=self.receiver,
            receiver=self.sender,
            task=self.task,
            response=response,
            status=status,
            conversation_id=self.conversation_id,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "task": self.task,
            "response": self.response,
            "status": self.status,
            "timestamp": self.timestamp,
            "conversation_id": self.conversation_id,
            "metadata": self.metadata or {},
        }
