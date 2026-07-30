import logging
from typing import Optional

from agents.team.communication import TeamMessage, MessageType
from agents.team.evidence import EvidencePool, AgentFinding
from agents.team.specialists import SpecialistAgent

logger = logging.getLogger("agents.team.coordinator")

CATEGORY_KEYWORDS = {
    "malware": ["malware", "virus", "trojan", "ransomware", "backdoor", "payload", "pe file", "exe", "dll"],
    "web": ["web", "http", "url", "xss", "sql injection", "csrf", "api", "endpoint", "cookie", "session"],
    "crypto": ["encrypt", "decrypt", "cipher", "hash", "base64", "rsa", "aes", "xor", "crypto", "key"],
    "forensics": ["forensic", "metadata", "exif", "disk image", "memory dump", "artifact", "stego",
                   "steganography", "hidden", "timeline", "log", "carving"],
}


class CoordinatorAgent:
    name = "coordinator_agent"

    def __init__(self, specialists: Optional[dict[str, SpecialistAgent]] = None):
        self.specialists: dict[str, SpecialistAgent] = specialists or {}
        self._evidence_pool = EvidencePool()
        self._messages: list[TeamMessage] = []

    def register_specialist(self, agent: SpecialistAgent) -> None:
        self.specialists[agent.name] = agent
        logger.info("Registered specialist: %s (category=%s, capabilities=%s)",
                     agent.name, agent.category, agent.capabilities)

    def register_specialists(self, agents: list[SpecialistAgent]) -> None:
        for agent in agents:
            self.register_specialist(agent)

    async def coordinate(self, task: str, context: Optional[dict] = None) -> dict:
        logger.info("Coordinator coordinating: %.60s", task)
        self._evidence_pool.clear()
        self._messages.clear()

        categories = self._classify(task, context)

        selected = self._select_agents(categories)
        if not selected:
            selected = list(self.specialists.values())
            logger.info("No category-specific agents selected, dispatching to all %d specialists", len(selected))

        findings = await self._delegate_and_collect(selected, task, context)
        self._evidence_pool.add_findings(findings)

        consolidated = self._resolve_findings(findings)
        report = self._evidence_pool.get_consolidated_report()

        return {
            "task": task,
            "categories_identified": categories,
            "agents_dispatched": [a.name for a in selected],
            "findings": [f.to_dict() for f in findings],
            "consolidated": consolidated,
            "evidence_pool": report,
            "message_log": [
                {"type": m.type.value, "sender": m.sender, "target": m.target, "status": m.status}
                for m in self._messages
            ],
        }

    def _classify(self, task: str, context: Optional[dict] = None) -> dict[str, float]:
        text = task.lower()
        if context:
            for v in context.values():
                text += " " + str(v).lower()

        scores: dict[str, float] = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(2.0 if kw in text else 0.0 for kw in keywords)
            if score > 0:
                scores[category] = score

        if not scores:
            scores["general"] = 1.0

        total = sum(scores.values()) or 1
        return {cat: round(s / total, 2) for cat, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)}

    def _select_agents(self, categories: dict[str, float]) -> list[SpecialistAgent]:
        selected: list[SpecialistAgent] = []
        assigned_names: set[str] = set()

        for cat in categories:
            for agent in self.specialists.values():
                if agent.name in assigned_names:
                    continue
                if agent.category == cat:
                    selected.append(agent)
                    assigned_names.add(agent.name)

        return selected

    async def _delegate_and_collect(
        self,
        agents: list[SpecialistAgent],
        task: str,
        context: Optional[dict] = None,
    ) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        task_id = task[:20]

        for agent in agents:
            msg = TeamMessage(
                type=MessageType.TASK,
                sender=self.name,
                target=agent.name,
                payload=f"[{agent.category.upper()} ANALYSIS] {task}",
                task_id=task_id,
                metadata=context,
            )
            self._messages.append(msg)
            logger.info("Delegating to %s (category=%s)", agent.name, agent.category)

            try:
                finding = await agent.analyze(msg.payload, context)
                findings.append(finding)
                self._messages.append(TeamMessage(
                    type=MessageType.FINDING,
                    sender=agent.name,
                    target=self.name,
                    payload=finding.findings[0] if finding.findings else "",
                    evidence=finding.evidence,
                    confidence=finding.confidence,
                    task_id=task_id,
                    status="completed",
                ))
            except Exception as e:
                logger.error("Specialist %s failed: %s", agent.name, e)
                self._messages.append(TeamMessage(
                    type=MessageType.STATUS,
                    sender=agent.name,
                    target=self.name,
                    payload=str(e),
                    task_id=task_id,
                    status="failed",
                ))

        return findings

    def _resolve_findings(self, findings: list[AgentFinding]) -> dict:
        if not findings:
            return {"resolution": "no_findings", "summary": ""}

        ranked = sorted(findings, key=lambda f: f.confidence, reverse=True)
        top = ranked[0]

        all_evidence = list({e for f in findings for e in f.evidence})
        all_tools = list({t for f in findings for t in f.tools_used})
        all_findings_text = [f for f2 in findings for f in f2.findings]

        return {
            "resolution": "consensus" if len(findings) > 1 else "single_agent",
            "lead_agent": top.agent_name,
            "lead_confidence": top.confidence,
            "all_findings": all_findings_text,
            "consolidated_evidence": all_evidence,
            "tools_used": all_tools,
            "summary": top.findings[0] if top.findings else "",
        }
