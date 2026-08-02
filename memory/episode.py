"""CTF episode capture — rich record of a single challenge attempt.

An episode is the unit of episodic memory. It captures everything useful
about one challenge attempt so a later attempt can reuse the successful
techniques and avoid the failed ones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("memory.episode")

_COMMAND_HINTS = [
    "strings", "python", "python3", "curl", "wget", "binwalk", "exiftool",
    "file ", "unzip", "tar ", "xxd", "hexdump", "base64", "openssl",
    "nc ", "nmap", "grep", "chmod", "objdump", "readelf", "gdb", "john",
    "hashcat", "steghide", "zsteg", "pngcheck", "volatility", "tshark",
    "tcpdump", "whois", "dig ", "hydra", "sqlmap", "jwt", "fcrackzip",
]


@dataclass
class CTFEpisode:
    challenge_id: str
    category: str
    difficulty: str
    status: str
    description: str = ""
    initial_plan: list = field(default_factory=list)
    agents_used: list = field(default_factory=list)
    skills_selected: list = field(default_factory=list)
    tools_used: list = field(default_factory=list)
    actions_commands: list = field(default_factory=list)
    successful_techniques: list = field(default_factory=list)
    failed_approaches: list = field(default_factory=list)
    final_solution_reasoning: str = ""
    verification_result: Optional[dict] = None
    flag_result: Optional[str] = None
    confidence: float = 0.0
    failure_reason: Optional[str] = None
    execution_time: float = 0.0
    attempts: int = 1

    @property
    def solved(self) -> bool:
        return self.status == "solved"

    def to_dict(self) -> dict:
        return {
            "challenge_id": self.challenge_id,
            "category": self.category,
            "difficulty": self.difficulty,
            "status": self.status,
            "description": self.description,
            "initial_plan": self.initial_plan,
            "agents_used": self.agents_used,
            "skills_selected": self.skills_selected,
            "tools_used": self.tools_used,
            "actions_commands": self.actions_commands,
            "successful_techniques": self.successful_techniques,
            "failed_approaches": self.failed_approaches,
            "final_solution_reasoning": self.final_solution_reasoning,
            "verification_result": self.verification_result,
            "flag_result": self.flag_result,
            "confidence": self.confidence,
            "failure_reason": self.failure_reason,
            "execution_time": self.execution_time,
            "attempts": self.attempts,
        }


def build_episode_from_supervisor_output(output: dict) -> Optional[CTFEpisode]:
    """Build a rich episode from a SupervisorAgent.run() result dict."""
    if not output:
        return None

    challenge = output.get("challenge") or {}
    flag_ver = output.get("flag_verification") or {}
    verification = output.get("verification") or {}
    learning_report = output.get("learning_report") or {}
    agent_results = output.get("agent_results") or []
    plan = output.get("plan") or []

    status = "solved" if flag_ver.get("status") == "PASS" else "failed"

    agents_used = list({r.get("agent", "") for r in agent_results if r.get("agent")})
    skills_selected = [
        s.get("name", s.get("description", ""))
        for s in learning_report.get("skills_used", [])
        if s
    ]

    techniques, commands, failed = _extract_from_agent_results(agent_results)

    reasoning = _extract_reasoning(output, agent_results)

    return CTFEpisode(
        challenge_id=challenge.get("id") or challenge.get("name", ""),
        category=challenge.get("category", ""),
        difficulty=challenge.get("difficulty", ""),
        status=status,
        description=output.get("request", ""),
        initial_plan=list(plan) if isinstance(plan, list) else [],
        agents_used=agents_used,
        skills_selected=skills_selected,
        tools_used=learning_report.get("tools_used", []) or [],
        actions_commands=commands,
        successful_techniques=techniques,
        failed_approaches=failed,
        final_solution_reasoning=reasoning,
        verification_result=verification if isinstance(verification, dict) else None,
        flag_result=flag_ver.get("status"),
        confidence=verification.get("confidence_score", 0.0)
        if isinstance(verification, dict) else 0.0,
        failure_reason=output.get("failure_reason"),
        execution_time=float(flag_ver.get("execution_time", 0) or 0),
    )


def _extract_from_agent_results(agent_results: list) -> tuple[list, list, list]:
    techniques: list = []
    commands: list = []
    failed: list = []

    for r in agent_results:
        response = r.get("response", "") or ""
        status = r.get("status", "")
        agent = r.get("agent", "unknown")

        if status == "failed":
            failed.append(f"{agent}: {response[:200]}")
            continue

        for line in response.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if any(hint in lower for hint in _COMMAND_HINTS):
                commands.append(stripped[:200])

        if "[Tool Execution Evidence]" in response or any(
            hint in response.lower() for hint in ["found", "extracted", "decoded", "cracked"]
        ):
            techniques.append(f"{agent}: {response[:300]}")

    return techniques, commands, failed


def _extract_reasoning(output: dict, agent_results: list) -> str:
    final_response = output.get("final_response", "") or ""
    if final_response:
        return final_response[:1000]

    reasoning_parts = []
    for r in agent_results:
        response = (r.get("response", "") or "").strip()
        if response:
            reasoning_parts.append(f"{r.get('agent', 'unknown')}: {response[:300]}")
    return "\n".join(reasoning_parts)[:2000]
