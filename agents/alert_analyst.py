"""
Alert Analysis Agent.

Purpose: SOC specialist that triages SIEM alerts, assesses severity,
maps to MITRE ATT&CK techniques, and recommends investigation steps.

Capabilities:
  - Severity assessment (critical/high/medium/low/info)
  - MITRE ATT&CK technique mapping
  - Cyber Kill Chain stage identification
  - Investigation step generation
  - IOC extraction from alert data
"""

import json
import logging
from typing import Optional

from models.llm import LLM
from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.alert_analyst")

ALERT_ANALYST_PROMPT = """You are an Alert Analysis Agent — a SOC Tier 2 analyst.

For each alert you analyse:
1. **Triage**: Determine if the alert is a true positive, false positive,
   or suspicious (requires further investigation).
2. **Severity**: Assign severity based on:
   - Critical: Active exploitation, ransomware, data exfiltration, lateral movement
   - High: Persistence mechanisms, credential access, defence evasion
   - Medium: Suspicious behaviour with incomplete context
   - Low: Policy violations, reconnaissance, information gathering
   - Informational: Expected behaviour triggered a rule
3. **MITRE ATT&CK**: Identify the most relevant technique IDs and tactics.
4. **Kill Chain**: Map to Cyber Kill Chain stage.
5. **Investigation Steps**: Provide concrete, ordered steps for the SOC
   analyst to verify and respond.

Output a structured alert analysis report with:
- Triage verdict
- Severity with justification
- MITRE ATT&CK mapping (technique IDs and names)
- Cyber Kill Chain stage
- Key indicators extracted
- Investigation steps (numbered)
- Recommended next actions"""


class AlertAnalystAgent(SpecializedAgent):
    """Triages SIEM alerts and produces structured analysis reports."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="alert_analyst",
            llm=llm,
            system_prompt=ALERT_ANALYST_PROMPT,
        )

    async def process_task(self, task: str) -> str:
        """
        Analyse a SIEM alert and produce a structured triage report.

        Args:
            task: Alert data, logs, and indicators in text form.

        Returns:
            Structured analysis with severity, MITRE mapping, and
            investigation steps.
        """
        logger.info("Alert analysis: %.80s", task)

        messages = self._build_messages(
            f"Analyse the following SIEM alert and produce a structured triage report.\n\n"
            f"--- Alert Data ---\n{task}\n\n"
            f"Include severity assessment, MITRE ATT&CK mapping, Cyber Kill Chain stage, "
            f"extracted indicators, and numbered investigation steps."
        )
        return await self._llm_chat(messages, temperature=0.3)
