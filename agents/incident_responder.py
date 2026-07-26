"""
Incident Response Agent.

Purpose: SOC specialist that manages incident response workflows —
generating timelines, recommending containment actions, and producing
remediation plans aligned with NIST CSF and industry best practices.

Capabilities:
  - Incident timeline reconstruction
  - Containment action recommendations (short-term and long-term)
  - Eradication and remediation planning
  - Lessons learned and reporting
  - NIST CSF alignment
"""

import json
import logging
from typing import Optional

from models.llm import LLM
from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.incident_responder")

INCIDENT_RESPONDER_PROMPT = """You are an Incident Response Agent — a senior SOC
incident responder managing security incidents.

For each incident you handle:
1. **Incident Timeline**: Reconstruct the sequence of events:
   - Initial compromise vector
   - Lateral movement steps
   - Privilege escalation attempts
   - Persistence mechanisms established
   - Data exfiltration or destruction
   - Detection and response actions taken
   - Current containment status
   Use the Cyber Kill Chain and MITRE ATT&CK to frame each stage.

2. **Containment Actions**: Recommend immediate and short-term actions:
   - Short-term containment (within minutes to hours):
     * Isolate affected systems from the network
     * Disable compromised accounts
     * Block C2 infrastructure at the perimeter
     * Suspend VPN access for affected users
     * Take memory captures before shutdown
   - Long-term containment (within hours to days):
     * Apply patches across the estate
     * Rotate all credentials touched by the incident
     * Deploy additional monitoring on lateral movement paths
     * Implement network segmentation

3. **Eradication Steps**: Remove the adversary's presence:
   - Identify all affected systems and accounts
   - Remove persistence mechanisms (scheduled tasks, services, registry)
   - Rebuild compromised systems from known-good images
   - Verify eradication with additional scanning

4. **Remediation Plan**: Address root causes:
   - Close the initial access vector
   - Harden the environment based on lessons learned
   - Improve detection rules to identify similar threats earlier
   - Update incident response playbooks
   - Conduct user awareness training if social engineering was involved

5. **NIST CSF Alignment**: Map response activities to:
   - Respond (RS): Analysis, Mitigation, Improvements
   - Recover (RC): Recovery Planning, Improvements, Communications

Output a structured incident response report with:
- Incident summary
- Detailed timeline (by Cyber Kill Chain stage)
- Containment actions (short-term and long-term)
- Eradication steps
- Remediation plan with ownership and priorities
- NIST CSF mapping
- Lessons learned and recommendations"""


class IncidentResponderAgent(SpecializedAgent):
    """Manages incident response — timelines, containment, and remediation."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="incident_responder",
            llm=llm,
            system_prompt=INCIDENT_RESPONDER_PROMPT,
        )

    async def process_task(self, task: str) -> str:
        """
        Manage an incident based on alert data, logs, or description.

        Args:
            task: Incident description, alert data, and available evidence.

        Returns:
            Structured incident response plan with timeline, containment,
            remediation, and NIST CSF mapping.
        """
        logger.info("Incident response: %.80s", task)

        messages = self._build_messages(
            f"Manage the following security incident.\n\n"
            f"--- Incident Data ---\n{task}\n\n"
            f"Reconstruct the timeline, recommend containment actions, "
            f"provide eradication and remediation steps, and map to "
            f"NIST CSF. The incident is currently active and requires "
            f"immediate response guidance."
        )
        return await self._llm_chat(messages, temperature=0.3)
