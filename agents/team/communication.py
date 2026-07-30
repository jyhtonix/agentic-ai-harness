import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


class MessageType(str, enum.Enum):
    TASK = "TASK"
    FINDING = "FINDING"
    EVIDENCE = "EVIDENCE"
    STATUS = "STATUS"
    CANCEL = "CANCEL"
    ACK = "ACK"


@dataclass
class TeamMessage:
    type: MessageType
    sender: str
    target: str
    payload: str = ""
    evidence: Optional[list[str]] = None
    confidence: float = 1.0
    task_id: str = ""
    status: str = "pending"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Optional[dict] = None
