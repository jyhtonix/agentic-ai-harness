"""Agent debate mechanism for resolving conflicting specialist findings."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from agents.team.evidence import AgentFinding

logger = logging.getLogger("agents.team.debate")


@dataclass
class DebateArgument:
    agent_name: str
    position: str
    evidence: list[str]
    confidence: float

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "position": self.position,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
        }


@dataclass
class ConsensusFinding:
    topic: str
    consensus: str
    confidence: float
    arguments: list[DebateArgument] = field(default_factory=list)
    selected_strategy: str = ""
    dissenting_opinions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "consensus": self.consensus,
            "confidence": self.confidence,
            "arguments": [a.to_dict() for a in self.arguments],
            "selected_strategy": self.selected_strategy,
            "dissenting_opinions": list(self.dissenting_opinions),
        }


class AgentDebate:
    def __init__(self):
        self._arguments: dict[str, list[DebateArgument]] = {}

    def submit_argument(self, topic: str, argument: DebateArgument) -> None:
        if topic not in self._arguments:
            self._arguments[topic] = []
        self._arguments[topic].append(argument)
        logger.debug("Debate argument submitted by %s on '%s' (conf=%.2f)",
                     argument.agent_name, topic, argument.confidence)

    def submit_finding(self, topic: str, finding: AgentFinding) -> None:
        position = finding.findings[0] if finding.findings else "No finding"
        arg = DebateArgument(
            agent_name=finding.agent_name,
            position=position,
            evidence=finding.evidence,
            confidence=finding.confidence,
        )
        self.submit_argument(topic, arg)

    def resolve(self, topic: str) -> Optional[ConsensusFinding]:
        args = self._arguments.get(topic, [])
        if not args:
            return None

        sorted_args = sorted(args, key=lambda a: a.confidence, reverse=True)
        top = sorted_args[0]

        dissenting = [
            a.position for a in sorted_args[1:]
            if self._conflicts(a.position, top.position)
        ]

        all_evidence = list({e for a in args for e in a.evidence})

        return ConsensusFinding(
            topic=topic,
            consensus=top.position,
            confidence=top.confidence,
            arguments=sorted_args,
            selected_strategy=top.position,
            dissenting_opinions=dissenting,
        )

    def get_arguments(self, topic: str) -> list[DebateArgument]:
        return list(self._arguments.get(topic, []))

    def clear(self, topic: str) -> None:
        self._arguments.pop(topic, None)

    def clear_all(self) -> None:
        self._arguments.clear()

    @staticmethod
    def _conflicts(a: str, b: str) -> bool:
        a_lower = a.lower()
        b_lower = b.lower()
        words_a = set(a_lower.split())
        words_b = set(b_lower.split())
        common = words_a & words_b
        if not common and words_a and words_b:
            return True
        return len(common) / max(len(words_a | words_b), 1) < 0.3
