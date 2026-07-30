import logging
import re
from enum import Enum
from typing import Optional

from challenges_engine.models import ChallengeDefinition

logger = logging.getLogger("challenges_engine.verifier")


class FlagStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class FlagVerificationResult:
    def __init__(
        self,
        status: FlagStatus,
        method: str = "",
        detail: str = "",
        student_flag: str = "",
    ):
        self.status = status
        self.method = method
        self.detail = detail
        self.student_flag = student_flag

    def __repr__(self):
        return f"FlagVerificationResult(status='{self.status}', method='{self.method}')"


class FlagVerifier:
    def verify(
        self,
        challenge: ChallengeDefinition,
        agent_response: str = "",
        tool_outputs: Optional[list[dict]] = None,
    ) -> FlagVerificationResult:
        if not challenge or not challenge.expected_flag:
            return FlagVerificationResult(
                FlagStatus.ERROR, "none",
                "Challenge has no expected flag configured",
            )

        method = challenge.verification.get("type", "exact_flag") if isinstance(challenge.verification, dict) else "exact_flag"

        if method == "regex":
            return self._verify_regex(challenge, agent_response, tool_outputs)
        elif method == "evidence":
            return self._verify_evidence(challenge, agent_response, tool_outputs)
        else:
            return self._verify_exact(challenge, agent_response, tool_outputs)

    def _verify_exact(
        self,
        challenge: ChallengeDefinition,
        agent_response: str,
        tool_outputs: Optional[list[dict]],
    ) -> FlagVerificationResult:
        expected = challenge.expected_flag.strip()
        candidates = self._extract_candidates(agent_response, tool_outputs)

        for candidate in candidates:
            if candidate.strip() == expected:
                return FlagVerificationResult(
                    FlagStatus.PASS, "exact_flag",
                    f"Exact match found: {expected}",
                    candidate,
                )

        return FlagVerificationResult(
            FlagStatus.FAIL, "exact_flag",
            f"No exact match for expected flag: {expected}",
            candidates[0] if candidates else "",
        )

    def _verify_regex(
        self,
        challenge: ChallengeDefinition,
        agent_response: str,
        tool_outputs: Optional[list[dict]],
    ) -> FlagVerificationResult:
        expected = challenge.expected_flag.strip()
        flag_format = challenge.flag_format or ""

        all_text = self._collect_text(agent_response, tool_outputs)

        if flag_format:
            try:
                pattern = re.compile(flag_format)
                matches = pattern.findall(all_text)
                for match in matches:
                    if match.strip() == expected:
                        return FlagVerificationResult(
                            FlagStatus.PASS, "regex",
                            f"Regex match found: {expected}",
                            match,
                        )
                    full_match = match if isinstance(match, str) else match[0]
                    if full_match.strip() == expected:
                        return FlagVerificationResult(
                            FlagStatus.PASS, "regex",
                            f"Regex match found: {expected}",
                            full_match,
                        )
                if matches:
                    return FlagVerificationResult(
                        FlagStatus.FAIL, "regex",
                        f"Regex matched but none match expected flag",
                        matches[0] if isinstance(matches[0], str) else matches[0][0],
                    )
            except re.error as e:
                return FlagVerificationResult(
                    FlagStatus.ERROR, "regex",
                    f"Regex error: {e}",
                )

        if expected in all_text:
            return FlagVerificationResult(
                FlagStatus.PASS, "regex",
                f"Expected flag found in text: {expected}",
                expected,
            )

        return FlagVerificationResult(
            FlagStatus.FAIL, "regex",
            f"Expected flag not found: {expected}",
        )

    def _verify_evidence(
        self,
        challenge: ChallengeDefinition,
        agent_response: str,
        tool_outputs: Optional[list[dict]],
    ) -> FlagVerificationResult:
        expected = challenge.expected_flag.strip()
        all_text = self._collect_text(agent_response, tool_outputs)

        tool_evidence = ""
        if tool_outputs:
            for t in tool_outputs:
                output = t.get("output", "")
                tool_name = t.get("tool", "unknown")
                if expected in output:
                    return FlagVerificationResult(
                        FlagStatus.PASS, "evidence",
                        f"Flag found in {tool_name} output",
                        expected,
                    )
                if output:
                    tool_evidence += output + "\n"

        if expected in agent_response:
            return FlagVerificationResult(
                FlagStatus.PASS, "evidence",
                "Flag found in agent response with evidence context",
                expected,
            )

        if expected in all_text:
            return FlagVerificationResult(
                FlagStatus.PASS, "evidence",
                "Flag found in collected evidence",
                expected,
            )

        return FlagVerificationResult(
            FlagStatus.FAIL, "evidence",
            f"Expected flag not found in any evidence source: {expected}",
        )

    @staticmethod
    @staticmethod
    def _extract_candidates(agent_response: str, tool_outputs: Optional[list[dict]]) -> list[str]:
        candidates = []
        if agent_response:
            candidates.append(agent_response)
            import re
            flags = re.findall(r'(?:CTF\{[^}]+\}|flag\{[^}]+\}|FLAG\{[^}]+\})', agent_response)
            candidates.extend(flags)
        if tool_outputs:
            for t in tool_outputs:
                output = t.get("output", "")
                if output:
                    candidates.append(output)
                    for line in output.split("\n"):
                        line = line.strip()
                        if line and ("CTF{" in line or "flag{" in line or "FLAG{" in line):
                            candidates.append(line)
                            flags = re.findall(r'(?:CTF\{[^}]+\}|flag\{[^}]+\}|FLAG\{[^}]+\})', line)
                            candidates.extend(flags)
        return candidates

    @staticmethod
    def _collect_text(agent_response: str, tool_outputs: Optional[list[dict]]) -> str:
        parts = []
        if agent_response:
            parts.append(agent_response)
        if tool_outputs:
            for t in tool_outputs:
                output = t.get("output", "")
                if output:
                    parts.append(output)
        return "\n".join(parts)
