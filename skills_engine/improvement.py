"""Skill Improvement Proposal Generator."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("skills_engine.improvement")

SKILL_TEMPLATES = {
    "pe-analysis": {
        "name": "PE Analysis",
        "description": "Analyze Portable Executable file format, headers, sections, and imports.",
        "topics": ["PE header structure", "section table analysis", "import/export tables",
                   "resource directory", "relocation data"],
        "tools": ["file", "python"],
    },
    "rsa-fundamentals": {
        "name": "RSA Cryptanalysis",
        "description": "Analyze RSA parameters, identify weaknesses, and apply attacks.",
        "topics": ["key generation", "modulus factorization", "small exponent attacks",
                   "padding oracle", "Wiener attack"],
        "tools": ["python"],
    },
    "web-security": {
        "name": "Web Security Assessment",
        "description": "Identify and exploit common web vulnerabilities.",
        "topics": ["OWASP Top 10", "authentication bypass", "injection attacks",
                   "SSRF", "SSTI"],
        "tools": ["curl", "python"],
    },
    "memory-forensics": {
        "name": "Memory Forensics",
        "description": "Analyze memory dumps for evidence of compromise.",
        "topics": ["process analysis", "network connections", "registry hives",
                   "DLL injection detection", "rootkit identification"],
        "tools": ["python", "strings"],
    },
}

DEFAULT_TEMPLATE = {
    "name": "Custom Skill",
    "description": "Custom skill definition for identified capability gap.",
    "topics": ["topic 1", "topic 2", "topic 3"],
    "tools": [],
}


class SkillImprovementProposal:
    def __init__(self):
        self._proposals: list[dict] = []

    def generate(self, detected_gap: str, category: str = "", confidence: float = 0.5) -> dict:
        key = self._match_template(detected_gap)
        template = SKILL_TEMPLATES.get(key, DEFAULT_TEMPLATE)
        skill_name = detected_gap.replace("_", "-").replace(" ", "-").lower()

        proposal = {
            "proposed_skill_name": skill_name,
            "category": category,
            "title": template["name"],
            "description": template["description"],
            "topics_to_cover": template["topics"],
            "recommended_tools": template["tools"],
            "confidence": round(confidence, 3),
            "urgency": "high" if confidence > 0.8 else "medium",
        }
        self._proposals.append(proposal)
        return proposal

    def generate_batch(self, gaps: list[dict]) -> list[dict]:
        proposals = []
        for gap_info in gaps:
            gap = gap_info.get("gap", "")
            category = gap_info.get("category", "")
            confidence = min(0.5 + 0.1 * gap_info.get("occurrences", 1), 0.95)
            proposal = self.generate(gap, category, confidence)
            proposals.append(proposal)
        return proposals

    def get_all_proposals(self) -> list[dict]:
        return list(self._proposals)

    def clear(self) -> None:
        self._proposals.clear()

    def format_report(self) -> str:
        if not self._proposals:
            return "No skill improvement proposals generated."

        lines = ["Skill Improvement Proposals:", "=" * 40]
        for i, p in enumerate(self._proposals, 1):
            lines.append(f"\n{i}. {p['title']} ({p['proposed_skill_name']})")
            lines.append(f"   Category: {p['category']}")
            lines.append(f"   Urgency: {p['urgency']}")
            lines.append(f"   Confidence: {p['confidence']:.0%}")
            lines.append(f"   Description: {p['description']}")
            lines.append(f"   Topics: {', '.join(p['topics_to_cover'][:4])}")
            lines.append(f"   Tools: {', '.join(p['recommended_tools'])}")
        return "\n".join(lines)

    @staticmethod
    def _match_template(gap: str) -> str:
        gap_lower = gap.lower()
        for key in SKILL_TEMPLATES:
            if key in gap_lower or gap_lower in key:
                return key
            words = key.replace("-", " ").split()
            if any(w in gap_lower for w in words):
                return key
        return ""
