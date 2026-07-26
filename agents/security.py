"""
Security Agent.

Purpose: Analyses code and architecture for security vulnerabilities.
This agent is the security specialist — it reviews code, identifies
common vulnerability patterns, and recommends mitigations.

Capabilities:
  - Static code analysis for security issues
  - OWASP Top 10 vulnerability identification
  - Input validation and sanitisation review
  - Authentication/authorisation flow analysis
  - Dependency vulnerability awareness
  - Remediation recommendations
"""

import logging
from typing import Optional

from models.llm import LLM
from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.security")

SECURITY_SYSTEM_PROMPT = """You are a Security Agent. You analyse code and
architecture for security vulnerabilities.

For each security review:
1. Identify potential vulnerabilities (OWASP Top 10, CWE categories)
2. Assess the severity and exploitability of each finding
3. Provide specific remediation steps
4. Prioritise findings by risk level
5. Consider: injection, broken auth, data exposure, XXE, broken access
   control, misconfiguration, XSS, insecure deserialisation, known
   vulnerabilities, insufficient logging

Output a structured security report with:
- Critical findings (must fix)
- High findings (should fix)
- Medium findings (consider fixing)
- Low / Informational findings
- Summary of overall security posture"""


class SecurityAgent(SpecializedAgent):
    """Analyses security vulnerabilities and recommends fixes."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="security",
            llm=llm,
            system_prompt=SECURITY_SYSTEM_PROMPT,
        )

    async def process_task(self, task: str) -> str:
        """Perform a security review on the given code or architecture."""
        logger.info("Security review: %.80s", task)

        messages = self._build_messages(
            f"Security review task:\n{task}\n\n"
            f"Analyse the code or architecture for vulnerabilities. "
            f"Provide a structured report with severity ratings and "
            f"remediation steps."
        )
        return await self._llm_chat(messages, temperature=0.3)
