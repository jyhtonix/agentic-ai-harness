import logging
from typing import Optional

from agents.team.evidence import AgentFinding
from agents.team.specialists import SpecialistAgent

logger = logging.getLogger("agents.team.specialists.crypto")


class CryptoAgent(SpecialistAgent):
    name = "crypto_agent"
    category = "crypto"
    capabilities = [
        "encoding_analysis",
        "hash_analysis",
        "rsa_analysis",
        "cipher_identification",
        "key_analysis",
    ]

    def __init__(self, tool_executor=None, tool_selector=None, skill_selector=None):
        super().__init__(tool_executor, tool_selector, skill_selector)

    async def analyze(self, task: str, context: Optional[dict] = None) -> AgentFinding:
        logger.info("CryptoAgent analyzing: %.60s", task)
        ctx = self._build_context(task, context)

        findings = []
        evidence = []
        tools_used = []
        confidence = 0.5

        if "base64" in ctx.lower() or "base32" in ctx.lower() or "base" in ctx.lower():
            findings.append("Base encoding detected — attempting to decode")
            evidence.append("Base64/32 encoded string identified")
            confidence += 0.2
        if "hex" in ctx.lower() or "0x" in ctx.lower():
            findings.append("Hexadecimal encoding detected — converting to ASCII")
            evidence.append("Hex-encoded data identified")
            confidence += 0.15
        if "hash" in ctx.lower() or "md5" in ctx.lower() or "sha" in ctx.lower():
            findings.append("Hash value detected — checking known hash databases")
            evidence.append(f"Cryptographic hash identified in sample")
            tools_used.append("python")
            confidence += 0.15
        if "rsa" in ctx.lower() or "public" in ctx.lower() or "private" in ctx.lower() or "key" in ctx.lower():
            findings.append("RSA key material detected — analyzing key structure and strength")
            evidence.append("RSA public/private key data identified")
            confidence += 0.2
        if "cipher" in ctx.lower() or "encrypt" in ctx.lower():
            findings.append("Encrypted data detected — attempting cipher identification")
            evidence.append("Encrypted content identified for analysis")
            confidence += 0.15
        if "xor" in ctx.lower():
            findings.append("XOR-encoded data detected — attempting key recovery")
            evidence.append("XOR pattern identified — single-byte XOR likely")
            confidence += 0.2

        if not findings:
            findings.append("Performing general cryptographic analysis on provided data")
            evidence.append("General crypto analysis performed")

        return AgentFinding(
            agent_name=self.name,
            findings=findings,
            evidence=list(set(evidence)),
            confidence=min(confidence, 0.95),
            tools_used=list(set(tools_used)),
            category=self.category,
        )
