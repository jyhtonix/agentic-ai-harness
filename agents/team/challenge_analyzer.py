"""Challenge Analyzer Agent — pre-execution challenge classification."""

import logging
from typing import Optional

logger = logging.getLogger("agents.team.challenge_analyzer")

COMPLEXITY_KEYWORDS = {
    "low": ["single", "basic", "simple", "direct", "one-step", "trivial"],
    "medium": ["multi-step", "combined", "intermediate", "layered", "chained"],
    "high": ["complex", "advanced", "obfuscated", "multi-stage", "polymorphic",
             "custom", "proprietary", "nested", "evasive"],
}

DOMAIN_KEYWORDS = {
    "crypto": ["encrypt", "decrypt", "cipher", "hash", "rsa", "aes", "xor", "crypto",
               "key", "plaintext", "ciphertext", "signature", "nonce", "padding"],
    "web": ["http", "web", "url", "xss", "csrf", "sql", "injection", "jwt", "cookie",
            "session", "api", "endpoint", "graphql", "websocket", "template"],
    "malware": ["malware", "virus", "trojan", "ransomware", "payload", "shellcode",
                "pe file", "dll", "driver", "rootkit", "packed", "obfuscated"],
    "forensics": ["forensic", "metadata", "exif", "disk", "memory", "pcap", "log",
                  "artifact", "timeline", "registry", "stego", "carving"],
    "reverse": ["reverse", "disassembly", "decompile", "debug", "rop", "gadget",
                "binary", "assembly", "firmware", "embedded"],
}


class ChallengeAnalyzerAgent:
    name = "challenge_analyzer"

    @staticmethod
    def analyze(description: str, required_skills: Optional[list[str]] = None) -> dict:
        text = description.lower()

        categories = ChallengeAnalyzerAgent._detect_domains(text)
        complexity = ChallengeAnalyzerAgent._estimate_complexity(text)
        agents = ChallengeAnalyzerAgent._recommend_agents(categories)
        tools = ChallengeAnalyzerAgent._recommend_tools(categories)
        strategy = ChallengeAnalyzerAgent._build_strategy(categories, complexity)

        return {
            "category": categories,
            "complexity": complexity,
            "required_agents": agents,
            "recommended_tools": tools,
            "recommended_strategy": strategy,
            "required_skills": required_skills or [],
            "is_multi_stage": len(categories) > 1 or complexity == "high",
        }

    @staticmethod
    def _detect_domains(text: str) -> list[str]:
        scores: dict[str, int] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = sum(2 for kw in keywords if kw in text)
            if score > 0:
                scores[domain] = score

        if not scores:
            return ["general"]

        max_score = max(scores.values())
        threshold = max_score * 0.5
        return sorted([d for d, s in scores.items() if s >= threshold])

    @staticmethod
    def _estimate_complexity(text: str) -> str:
        for level, keywords in COMPLEXITY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return level
        return "medium"

    @staticmethod
    def _recommend_agents(categories: list[str]) -> list[str]:
        agent_map = {
            "crypto": "CryptoAgent",
            "web": "WebSecurityAgent",
            "malware": "MalwareAnalysisAgent",
            "forensics": "ForensicsAgent",
            "reverse": "ReverseEngineeringAgent",
        }
        return [agent_map.get(cat, "GeneralPurposeAgent") for cat in categories]

    @staticmethod
    def _recommend_tools(categories: list[str]) -> list[str]:
        tool_map = {
            "crypto": ["python"],
            "web": ["curl", "python"],
            "malware": ["file", "strings", "python"],
            "forensics": ["exiftool", "strings", "python", "binwalk"],
            "reverse": ["python", "strings"],
        }
        tools = []
        for cat in categories:
            tools.extend(tool_map.get(cat, []))
        return list(set(tools))

    @staticmethod
    def _build_strategy(categories: list[str], complexity: str) -> str:
        if len(categories) >= 2:
            primary = categories[0]
            secondary = categories[1:]
            return (f"Analyze {primary} aspects first, then examine "
                    f"{' and '.join(secondary)}. This is a multi-stage challenge "
                    f"requiring coordinated specialist analysis.")
        if categories:
            return (f"Apply standard {categories[0]} analysis methodology. "
                    f"Start with reconnaissance, then apply known techniques, "
                    f"then verify and extract flag.")
        return "Apply general CTF solving methodology."
