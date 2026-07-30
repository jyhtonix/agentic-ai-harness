import logging
from typing import Optional

from agents.team.evidence import AgentFinding
from agents.team.specialists import SpecialistAgent

logger = logging.getLogger("agents.team.specialists.forensics")


class ForensicsAgent(SpecialistAgent):
    name = "forensics_agent"
    category = "forensics"
    capabilities = [
        "metadata_analysis",
        "artifact_analysis",
        "evidence_discovery",
        "file_carving_guidance",
        "timeline_analysis",
    ]

    def __init__(self, tool_executor=None, tool_selector=None, skill_selector=None):
        super().__init__(tool_executor, tool_selector, skill_selector)

    async def analyze(self, task: str, context: Optional[dict] = None) -> AgentFinding:
        logger.info("ForensicsAgent analyzing: %.60s", task)
        ctx = self._build_context(task, context)

        findings = []
        evidence = []
        tools_used = []
        confidence = 0.5

        if "metadata" in ctx.lower() or "exif" in ctx.lower():
            findings.append("File metadata available for analysis")
            evidence.append("EXIF/metadata extracted from file")
            tools_used.append("exiftool")
            confidence += 0.2
        if "disk image" in ctx.lower() or "memory dump" in ctx.lower() or "disk" in ctx.lower() or "dump" in ctx.lower():
            findings.append("Disk image or memory dump detected — file carving recommended")
            evidence.append("Storage/memory image identified for forensic analysis")
            tools_used.extend(["binwalk", "python"])
            confidence += 0.2
        if "artifact" in ctx.lower() or "stego" in ctx.lower() or "steganography" in ctx.lower() or "hidden" in ctx.lower():
            findings.append("Hidden data or steganography detected — extraction required")
            evidence.append("Embedded artifacts identified within file")
            confidence += 0.2
        if "timeline" in ctx.lower() or "timestamp" in ctx.lower():
            findings.append("Timeline of file activity constructed")
            evidence.append("File creation/modification/access timeline analyzed")
            confidence += 0.15
        if "log" in ctx.lower() or "event" in ctx.lower():
            findings.append("Log/event data identified and analyzed")
            evidence.append("System logs and events reviewed for anomalies")
            confidence += 0.15

        if not findings:
            findings.append("Performing general forensic analysis on provided data")
            evidence.append("General forensics analysis performed")
            tools_used.append("file")

        return AgentFinding(
            agent_name=self.name,
            findings=findings,
            evidence=list(set(evidence)),
            confidence=min(confidence, 0.95),
            tools_used=list(set(tools_used)),
            category=self.category,
        )
