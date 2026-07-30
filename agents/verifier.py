"""
Verification Agent.

Purpose: Framework-level verification layer that runs after execution
and before final synthesis. Reviews agent outputs for evidence quality,
flag format correctness, completeness, and likely hallucination.

Clean architecture: The Verifier depends only on the result dict format
and Pydantic models. It does not import any agent, LLM, or tool.
"""

import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger("agent.verifier")

MIN_RESPONSE_LENGTH = 20
UNSUPPORTED_PATTERNS = [
    "i think", "i believe", "i assume", "i guess",
    "probably", "possibly", "might be", "could be",
    "not sure", "uncertain", "maybe", "perhaps",
    "i don't know", "cannot determine", "insufficient",
]


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class Finding(BaseModel):
    step_index: int
    agent_name: str
    finding_type: str
    severity: str
    message: str


class VerificationResult(BaseModel):
    status: VerificationStatus
    confidence_score: float
    findings: list[Finding]
    issues: list[str]
    recommendations: list[str]


class VerificationAgent:
    def __init__(self):
        self._flag_patterns = [
            r"flag\{[^}]+\}",
            r"FLAG\{[^}]+\}",
            r"ctf\{[^}]+\}",
            r"CTF\{[^}]+\}",
        ]

    async def verify(
        self,
        request: str = "",
        plan: Optional[list[dict]] = None,
        agent_results: Optional[list[dict]] = None,
    ) -> VerificationResult:
        findings: list[Finding] = []
        issues: list[str] = []
        recommendations: list[str] = []

        results = agent_results or []
        plan_steps = plan or []

        if not results:
            issues.append("No agent results to verify")
            recommendations.append("Ensure at least one agent is dispatched")
            return VerificationResult(
                status=VerificationStatus.FAILED,
                confidence_score=0.0,
                findings=[],
                issues=issues,
                recommendations=recommendations,
            )

        flag_count = 0

        for result in results:
            step_idx = result.get("step", 0)
            agent_name = result.get("agent", "unknown")
            response = result.get("response", "")
            status = result.get("status", "")

            if status == "failed":
                findings.append(Finding(
                    step_index=step_idx,
                    agent_name=agent_name,
                    finding_type="execution_failure",
                    severity="error",
                    message=f"Step {step_idx} ({agent_name}) failed execution",
                ))

            self._check_empty_response(findings, step_idx, agent_name, response)
            self._check_evidence(findings, step_idx, agent_name, response)
            self._check_unsupported_claims(findings, step_idx, agent_name, response)
            flag_count += self._check_flag_format(findings, step_idx, agent_name, response)

        score = self._compute_confidence(findings, flag_count, len(results))
        issues = [f.message for f in findings if f.severity == "error"]
        recommendations = self._generate_recommendations(findings)

        status = self._determine_status(findings, score)

        return VerificationResult(
            status=status,
            confidence_score=round(score, 2),
            findings=findings,
            issues=issues,
            recommendations=recommendations,
        )

    def _check_empty_response(
        self,
        findings: list[Finding],
        step_idx: int,
        agent_name: str,
        response: str,
    ) -> None:
        stripped = response.strip()
        if not stripped:
            findings.append(Finding(
                step_index=step_idx,
                agent_name=agent_name,
                finding_type="empty_response",
                severity="error",
                message=f"Step {step_idx} ({agent_name}) returned an empty response",
            ))
        elif len(stripped) < MIN_RESPONSE_LENGTH:
            findings.append(Finding(
                step_index=step_idx,
                agent_name=agent_name,
                finding_type="minimal_response",
                severity="warning",
                message=f"Step {step_idx} ({agent_name}) returned a very short response ({len(stripped)} chars)",
            ))

    def _check_evidence(
        self,
        findings: list[Finding],
        step_idx: int,
        agent_name: str,
        response: str,
    ) -> None:
        lower = response.lower()
        evidence_indicators = [
            "because", "since", "as shown", "demonstrated",
            "based on", "according to", "evidence", "indicates",
            "analysis shows", "found that", "observed",
            "the output shows", "results indicate",
        ]
        found = any(indicator in lower for indicator in evidence_indicators)
        if not found and len(response.strip()) >= MIN_RESPONSE_LENGTH:
            findings.append(Finding(
                step_index=step_idx,
                agent_name=agent_name,
                finding_type="missing_evidence",
                severity="warning",
                message=f"Step {step_idx} ({agent_name}) lacks reasoning or evidence markers",
            ))

    def _check_unsupported_claims(
        self,
        findings: list[Finding],
        step_idx: int,
        agent_name: str,
        response: str,
    ) -> None:
        lower = response.lower()
        for pattern in UNSUPPORTED_PATTERNS:
            if pattern in lower:
                findings.append(Finding(
                    step_index=step_idx,
                    agent_name=agent_name,
                    finding_type="unsupported_claim",
                    severity="warning",
                    message=f"Step {step_idx} ({agent_name}) contains uncertain language: '{pattern}'",
                ))
                break

    def _check_flag_format(
        self,
        findings: list[Finding],
        step_idx: int,
        agent_name: str,
        response: str,
    ) -> int:
        import re
        flag_count = 0
        for pattern in self._flag_patterns:
            matches = re.findall(pattern, response)
            flag_count += len(matches)
            for match in matches:
                findings.append(Finding(
                    step_index=step_idx,
                    agent_name=agent_name,
                    finding_type="flag_format",
                    severity="info",
                    message=f"Step {step_idx} ({agent_name}) found flag: {match[:50]}",
                ))
        return flag_count

    def _compute_confidence(
        self,
        findings: list[Finding],
        flag_count: int,
        total_steps: int,
    ) -> float:
        score = 1.0

        for f in findings:
            if f.finding_type == "empty_response":
                score -= 0.3
            elif f.finding_type == "execution_failure":
                score -= 0.25
            elif f.finding_type == "minimal_response":
                score -= 0.15
            elif f.finding_type == "missing_evidence":
                score -= 0.1
            elif f.finding_type == "unsupported_claim":
                score -= 0.1

        if flag_count > 0 and total_steps > 0:
            score += min(0.15, flag_count * 0.05)

        return max(0.0, min(1.0, score))

    def _determine_status(
        self,
        findings: list[Finding],
        score: float,
    ) -> VerificationStatus:
        errors = [f for f in findings if f.severity == "error"]
        if errors:
            return VerificationStatus.FAILED
        if score < 0.6:
            return VerificationStatus.FAILED
        if score < 0.8:
            return VerificationStatus.NEEDS_REVIEW
        return VerificationStatus.PASSED

    @staticmethod
    def _generate_recommendations(findings: list[Finding]) -> list[str]:
        recs = []
        types = {f.finding_type for f in findings}
        if "empty_response" in types:
            recs.append("Review agents that returned empty responses")
        if "execution_failure" in types:
            recs.append("Check agent availability and retry configuration")
        if "missing_evidence" in types:
            recs.append("Request agents to include reasoning and evidence in responses")
        if "unsupported_claim" in types:
            recs.append("Encourage agents to provide confident, evidence-backed answers")
        return recs
