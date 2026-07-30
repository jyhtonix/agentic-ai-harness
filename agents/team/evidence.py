import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("agents.team.evidence")


@dataclass
class AgentFinding:
    agent_name: str
    findings: list[str]
    evidence: list[str]
    confidence: float = 0.5
    tools_used: list[str] = field(default_factory=list)
    category: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "findings": list(self.findings),
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "tools_used": list(self.tools_used),
            "category": self.category,
        }


class EvidencePool:
    def __init__(self):
        self._findings: list[AgentFinding] = []

    def add_finding(self, finding: AgentFinding) -> None:
        if not finding.findings:
            return
        for existing in self._findings:
            if self._duplicate(existing, finding):
                if finding.confidence > existing.confidence:
                    self._findings.remove(existing)
                    self._findings.append(finding)
                    logger.debug("Replaced lower-confidence duplicate finding from %s with %s",
                                 existing.agent_name, finding.agent_name)
                return
        self._findings.append(finding)
        logger.debug("Added finding from %s (confidence=%.2f)", finding.agent_name, finding.confidence)

    def add_findings(self, findings: list[AgentFinding]) -> None:
        for f in findings:
            self.add_finding(f)

    def get_all(self) -> list[AgentFinding]:
        return list(self._findings)

    def get_ranked(self) -> list[AgentFinding]:
        return sorted(self._findings, key=lambda x: x.confidence, reverse=True)

    def get_high_confidence(self, threshold: float = 0.7) -> list[AgentFinding]:
        return [f for f in self._findings if f.confidence >= threshold]

    def get_consolidated_report(self) -> dict:
        ranked = self.get_ranked()
        return {
            "total_findings": len(ranked),
            "agents_contributing": list({f.agent_name for f in ranked}),
            "top_finding": ranked[0].findings[0] if ranked else "",
            "top_confidence": ranked[0].confidence if ranked else 0.0,
            "findings": [f.to_dict() for f in ranked],
            "consolidated_evidence": list({
                e for f in ranked for e in f.evidence
            }),
        }

    def clear(self) -> None:
        self._findings.clear()

    def __len__(self) -> int:
        return len(self._findings)

    @staticmethod
    def _duplicate(a: AgentFinding, b: AgentFinding) -> bool:
        a_set = set(a.findings)
        b_set = set(b.findings)
        if not a_set or not b_set:
            return False
        overlap = a_set & b_set
        return len(overlap) / max(len(a_set), len(b_set)) >= 0.5
