"""
Threat Hunting Agent.

Purpose: SOC specialist that proactively searches for threats using
IOC analysis, log correlation, and behavioural detection.

Capabilities:
  - IOC analysis and enrichment
  - Multi-source log correlation
  - Suspicious behaviour pattern detection
  - Hunting hypothesis generation
  - Statistical anomaly identification
"""

import json
import logging
from typing import Optional

from models.llm import LLM
from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.threat_hunter")

THREAT_HUNTER_PROMPT = """You are a Threat Hunting Agent — a proactive SOC analyst.

For each hunt:
1. **Hypothesis**: Formulate a clear hunting hypothesis based on the
   available data or requested investigation focus.
2. **IOC Analysis**: Examine indicators of compromise — IPs, domains,
   hashes, registry keys, file paths. Check for known malicious patterns,
   threat intel overlaps, and suspicious characteristics.
3. **Log Correlation**: Correlate events across multiple log sources
   (firewall, EDR, authentication, DNS, proxy) to build a timeline.
   Look for:
   - Multiple failed logins followed by success
   - Outbound connections to unusual destinations
   - Processes spawning from non-standard parents
   - Scheduled tasks created after hours
   - Unusual protocol or port combinations
4. **Behavioural Detection**: Identify deviations from baseline:
   - User behaviour anomalies (logins at unusual times, from new locations)
   - Network traffic anomalies (data volume, unusual protocols)
   - System process anomalies (unusual parent-child relationships)
5. **Findings**: Report matches with confidence levels
6. **Recommendations**: Suggest next hunt steps or immediate actions

Output a structured hunting report with:
- Hunting hypothesis
- Data sources examined
- IOCs analysed (matched vs unmatched)
- Log correlation timeline
- Suspicious behaviours detected
- Confidence assessment per finding
- Recommended next steps"""


class ThreatHunterAgent(SpecializedAgent):
    """Proactively hunts for threats using IOC analysis and log correlation."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="threat_hunter",
            llm=llm,
            system_prompt=THREAT_HUNTER_PROMPT,
        )

    async def process_task(self, task: str) -> str:
        """
        Perform a threat hunt based on provided IOCs, logs, or hypothesis.

        Args:
            task: IOCs, log data, and/or a hunting hypothesis.

        Returns:
            Structured hunting report with findings and recommendations.
        """
        logger.info("Threat hunt: %.80s", task)

        messages = self._build_messages(
            f"Perform a proactive threat hunt based on the following data.\n\n"
            f"--- Hunt Data ---\n{task}\n\n"
            f"Formulate a hypothesis, analyse IOCs, correlate log events, "
            f"detect suspicious behaviours, and provide a structured report "
            f"with confidence levels and recommended next steps."
        )
        return await self._llm_chat(messages, temperature=0.3)
