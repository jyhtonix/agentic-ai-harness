"""Skill Gap Detector — automatically identifies missing skills from failure patterns."""

from __future__ import annotations

import logging
from typing import Optional

from benchmark_engine.results import BenchmarkResult
from benchmark_engine.failure import FailureAnalyzer

logger = logging.getLogger("benchmark_engine.skill_gap")

CATEGORY_SKILL_MAP = {
    "crypto": {
        "rsa": ["rsa-fundamentals", "rsa-attacks", "lattice-reduction"],
        "aes": ["aes-cbc", "aes-ctr", "aes-ecb"],
        "hash": ["hash-analysis", "hash-extension", "collision-finding"],
        "ecc": ["elliptic-curve", "pohlig-hellman", "ecdsa"],
        "encoding": ["base64-analysis", "xor-analysis", "encoding-identification"],
    },
    "web": {
        "injection": ["sql-injection", "command-injection", "template-injection"],
        "authentication": ["jwt-security", "oauth-security", "session-analysis"],
        "ssrf": ["ssrf-detection", "internal-network-enumeration"],
        "xss": ["xss-detection", "csp-bypass", "xss-exfiltration"],
        "api": ["graphql-security", "api-security", "rate-limiting-analysis"],
    },
    "malware": {
        "pe": ["pe-analysis", "import-analysis", "section-analysis"],
        "shellcode": ["shellcode-analysis", "xor-decoding", "rop-analysis"],
        "packer": ["packer-detection", "unpacking", "entropy-analysis"],
        "persistence": ["registry-persistence", "scheduled-task-analysis", "service-analysis"],
        "memory": ["memory-analysis", "process-injection", "dump-analysis"],
    },
    "forensics": {
        "disk": ["disk-forensics", "file-carving", "mft-analysis"],
        "memory": ["memory-forensics", "volatility-analysis", "dump-analysis"],
        "network": ["network-forensics", "pcap-analysis", "protocol-analysis"],
        "stego": ["steganography-detection", "lsb-analysis", "metadata-analysis"],
        "cloud": ["cloud-forensics", "aws-investigation", "log-analysis"],
    },
    "reverse": {
        "binary": ["binary-analysis", "disassembly", "control-flow-analysis"],
        "firmware": ["firmware-extraction", "embedded-analysis", "hardware-analysis"],
    },
}


class SkillGapDetector:
    def __init__(self, failure_analyzer: Optional[FailureAnalyzer] = None):
        self.failure_analyzer = failure_analyzer or FailureAnalyzer()
        self._gap_counts: dict[str, dict[str, int]] = {}

    def analyze(self, result: BenchmarkResult) -> dict:
        if result.solved:
            return {"gaps": [], "confidence": 0.0, "recommendation": ""}

        failure_category = result.failure_category
        if not failure_category:
            analysis = self.failure_analyzer.analyze(result)
            failure_category = analysis.get("category")
        if failure_category != "missing_skill":
            return {"gaps": [], "confidence": 0.0,
                    "recommendation": "Failure not skill-related"}

        category = result.category or "unknown"
        reason = (result.failure_reason or "").lower()

        detected_gaps = self._detect_gaps(category, reason)
        if category not in self._gap_counts:
            self._gap_counts[category] = {}
        for gap in detected_gaps:
            self._gap_counts[category][gap] = self._gap_counts[category].get(gap, 0) + 1

        confidence = min(0.5 + 0.1 * len(detected_gaps), 0.95)

        return {
            "gaps": detected_gaps,
            "confidence": round(confidence, 3),
            "recommendation": self._build_recommendation(category, detected_gaps),
            "category": category,
        }

    def get_summary(self) -> dict:
        summary = {}
        for category, gaps in self._gap_counts.items():
            sorted_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
            summary[category] = [
                {"gap": gap, "occurrences": count}
                for gap, count in sorted_gaps
            ]
        return summary

    def get_top_gaps(self, top_n: int = 5) -> list[dict]:
        all_gaps: list[dict] = []
        for category, gaps in self._gap_counts.items():
            for gap, count in gaps.items():
                all_gaps.append({"category": category, "gap": gap, "occurrences": count})
        all_gaps.sort(key=lambda x: x["occurrences"], reverse=True)
        return all_gaps[:top_n]

    def _detect_gaps(self, category: str, reason: str) -> list[str]:
        skill_map = CATEGORY_SKILL_MAP.get(category, {})
        gaps = []
        for domain, skills in skill_map.items():
            if domain in reason:
                gaps.extend(skills[:2])
        if not gaps:
            gaps = [f"{category}-advanced-analysis"]
        return gaps

    @staticmethod
    def _build_recommendation(category: str, gaps: list[str]) -> str:
        if not gaps:
            return f"Create comprehensive {category} skill pack"
        gap_list = ", ".join(gaps[:3])
        return (f"Missing skills detected for {category}: {gap_list}. "
                f"Create skill definitions covering these topics.")
