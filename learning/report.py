"""
Learning Report Generator.

Purpose: After execution and verification, generates structured learning
reports for educational feedback. Analyses skills used, execution quality,
and verification results to produce student-facing and instructor-facing
reports.

Clean architecture: Deterministic (no LLM calls). Depends on:
  - skills_engine models (skill dict format)
  - verification models (VerificationResult)
  - execution models (ExecutionResult)
"""

import hashlib
import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger("learning.report")

LEARNING_OBJECTIVE_TEMPLATES = {
    "web": "Understand and apply {skill} techniques for web-based challenges",
    "forensics": "Practice {skill} methods for analysing forensic evidence",
    "reverse": "Develop {skill} skills for reverse engineering binaries",
    "pwn": "Learn {skill} exploitation techniques for binary challenges",
    "crypto": "Apply {skill} cryptographic analysis methods",
    "osint": "Use {skill} open-source intelligence gathering techniques",
    "malware": "Analyse {skill} indicators and behavioural patterns",
    "ai-ml": "Apply {skill} machine learning techniques to cybersecurity",
    "misc": "Develop {skill} problem-solving approaches",
    "blockchain": "Understand {skill} security considerations in blockchain",
}

STUDENT_REPORT_TEMPLATE = """=== LEARNING REPORT ===

Challenge: {challenge_summary}
Difficulty Estimate: {difficulty_estimate}
Confidence Score: {confidence_score}/1.0

Skills Practiced:
{skills_practiced}

Learning Objectives:
{learning_objectives}

{verification_section}
Improvement Suggestions:
{improvement_suggestions}

=== END REPORT ==="""

INSTRUCTOR_SUMMARY_TEMPLATE = """=== INSTRUCTOR SUMMARY ===

Challenge ID: {challenge_id}
Summary: {challenge_summary}
Difficulty: {difficulty_estimate}
Overall Performance: {performance_label}

Skills Used ({skills_used_count}):
{skills_used_detail}

Skills Mastered:
{skills_mastered}

Skills Needing Improvement:
{skills_needing_improvement}

Verification Status: {verification_status}
Confidence Score: {confidence_score}/1.0

Training Recommendations:
{training_recommendations}

=== END INSTRUCTOR SUMMARY ==="""


class LearningReport(BaseModel):
    challenge_id: str
    challenge_summary: str
    skills_used: list[dict]
    skills_mastered: list[str]
    skills_needing_improvement: list[str]
    verification_result: Optional[dict] = None
    learning_objectives: list[str]
    recommendations: list[str]
    difficulty_estimate: str
    student_report: str = ""
    instructor_summary: str = ""


class LearningReportGenerator:
    def __init__(self):
        self._difficulty_keywords = {
            "beginner": ["basic", "intro", "simple", "easy", "fundamental"],
            "intermediate": ["intermediate", "medium", "moderate", "standard"],
            "advanced": ["advanced", "complex", "hard", "challenging", "difficult"],
            "expert": ["expert", "master", "extreme", "insane"],
        }

    def generate(
        self,
        request: str = "",
        skills_used: Optional[list[dict]] = None,
        verification_result: "Optional[VerificationResult]" = None,
        agent_results: Optional[list[dict]] = None,
        challenge_info: Optional[dict] = None,
        flag_result: Optional[dict] = None,
        tools_used: Optional[list[str]] = None,
    ) -> LearningReport:
        skills = skills_used or []
        results = agent_results or []
        challenge = challenge_info or {}
        tools = tools_used or []

        challenge_id = self._make_challenge_id(request)
        challenge_summary = self._summarise_challenge(request)
        skills_mastered, skills_needing = self._classify_skills(
            skills, verification_result, results,
        )
        learning_objectives = self._generate_objectives(skills)
        difficulty = self._estimate_difficulty(skills, results, verification_result)
        recommendations = self._make_recommendations(skills_needing, verification_result)
        recommendations += self._make_challenge_recommendations(challenge, flag_result)
        recommendations += self._make_tool_recommendations(tools, flag_result)

        vr_dict = verification_result.model_dump() if verification_result else None

        report = LearningReport(
            challenge_id=challenge_id,
            challenge_summary=challenge_summary,
            skills_used=skills,
            skills_mastered=skills_mastered,
            skills_needing_improvement=skills_needing,
            verification_result=vr_dict,
            learning_objectives=learning_objectives,
            recommendations=recommendations,
            difficulty_estimate=difficulty,
        )
        report.student_report = self._format_student_report(report, challenge, flag_result, tools)
        report.instructor_summary = self._format_instructor_summary(report, challenge, flag_result, tools)
        return report

    # ------------------------------------------------------------------
    # Internal analysis helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_challenge_id(request: str) -> str:
        raw = request.strip().lower()
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    @staticmethod
    def _summarise_challenge(request: str) -> str:
        return request.strip()[:120]

    def _classify_skills(
        self,
        skills: list[dict],
        verification_result: Optional["VerificationResult"],
        results: list[dict],
    ) -> tuple[list[str], list[str]]:
        mastered: list[str] = []
        needing: list[str] = []

        if verification_result:
            has_flag = any(
                f.finding_type == "flag_format"
                for f in verification_result.findings
            )
            has_errors = any(
                f.severity == "error"
                for f in verification_result.findings
            )
            score = verification_result.confidence_score

            for sk in skills:
                name = sk.get("name", sk.get("description", "unknown"))
                if has_flag and score >= 0.7 and not has_errors:
                    mastered.append(name)
                elif has_errors or score < 0.5:
                    needing.append(name)
                else:
                    mastered.append(name)

        if not mastered and not needing:
            for sk in skills:
                name = sk.get("name", sk.get("description", "unknown"))
                mastered.append(name)

        failed_steps = [r for r in results if r.get("status") == "failed"]
        for r in failed_steps:
            agent = r.get("agent", "unknown")
            if agent not in needing:
                needing.append(agent)

        return mastered, needing

    def _generate_objectives(self, skills: list[dict]) -> list[str]:
        if not skills:
            return ["Complete the challenge and analyse the outcome"]

        objectives = []
        for sk in skills:
            name = sk.get("name", "")
            category = sk.get("category", sk.get("subdomain", ""))
            template = LEARNING_OBJECTIVE_TEMPLATES.get(
                category,
                "Develop {skill} skills through practical application",
            )
            objectives.append(template.format(skill=name))
        return objectives

    def _estimate_difficulty(
        self,
        skills: list[dict],
        results: list[dict],
        verification_result: Optional["VerificationResult"],
    ) -> str:
        score = verification_result.confidence_score if verification_result else 1.0
        step_count = len(results)
        skill_count = len(skills)

        if score < 0.3:
            return "advanced"
        if step_count >= 5 or skill_count >= 4:
            return "advanced"
        if step_count >= 3 or skill_count >= 2:
            return "intermediate"
        return "beginner"

    def _make_recommendations(
        self,
        skills_needing: list[str],
        verification_result: Optional["VerificationResult"],
    ) -> list[str]:
        recs: list[str] = []
        if skills_needing:
            names = ", ".join(skills_needing[:3])
            recs.append(f"Focus on improving: {names}")

        if verification_result:
            for f in verification_result.findings:
                if f.finding_type == "empty_response":
                    recs.append("Practice providing complete, detailed answers")
                elif f.finding_type == "missing_evidence":
                    recs.append("Work on including evidence and reasoning in responses")
                elif f.finding_type == "unsupported_claim":
                    recs.append("Aim for confident, evidence-backed statements")
                elif f.finding_type == "flag_format":
                    recs.append("Continue practicing flag identification and extraction")

        if not recs:
            recs.append("Attempt more challenges to reinforce skills")

        return recs

    def _make_challenge_recommendations(
        self,
        challenge_info: dict,
        flag_result: Optional[dict],
    ) -> list[str]:
        recs = []
        if not flag_result:
            return recs
        status = flag_result.get("status", "")
        if status == "PASS":
            recs.append(f"Challenge '{challenge_info.get('name', '')}' flag correctly identified")
        elif status == "FAIL":
            recs.append(f"Flag verification failed for challenge '{challenge_info.get('name', '')}' — review the expected output")
        return recs

    @staticmethod
    def _make_tool_recommendations(
        tools_used: list[str],
        flag_result: Optional[dict],
    ) -> list[str]:
        recs = []
        if not tools_used:
            recs.append("Consider using more analysis tools to gather evidence")
            return recs
        recs.append(f"Tools utilized: {', '.join(tools_used)}")
        return recs

    # ------------------------------------------------------------------
    # Report format helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_student_report(
        report: LearningReport,
        challenge_info: Optional[dict] = None,
        flag_result: Optional[dict] = None,
        tools_used: Optional[list[str]] = None,
    ) -> str:
        skills_practiced = "\n".join(
            f"  - {s.get('name', s.get('description', 'unknown'))}"
            for s in report.skills_used
        ) if report.skills_used else "  (none recorded)"

        objectives = "\n".join(
            f"  - {o}" for o in report.learning_objectives
        ) if report.learning_objectives else "  (none specified)"

        v = report.verification_result or {}
        confidence = v.get("confidence_score", 0.0) if isinstance(v, dict) else 0.0

        issues = v.get("issues", []) if isinstance(v, dict) else []
        verification_section = (
            "Verification Notes:\n" + "\n".join(f"  - {issue}" for issue in issues)
            if issues
            else "Verification: No issues found."
        )

        suggestions = "\n".join(
            f"  - {r}" for r in report.recommendations
        ) if report.recommendations else "  (none)"

        if challenge_info:
            challenge_header = f"Challenge: {challenge_info.get('name', '')} ({challenge_info.get('category', '')})"
            suggestions = f"{challenge_header}\n{suggestions}"

        if flag_result:
            flag_line = f"Flag Status: {flag_result.get('status', 'UNKNOWN')} (method: {flag_result.get('method', 'none')})"
            suggestions = f"{flag_line}\n{suggestions}"

        if tools_used:
            tools_line = f"Tools Used: {', '.join(tools_used)}"
            suggestions = f"{tools_line}\n{suggestions}"

        return STUDENT_REPORT_TEMPLATE.format(
            challenge_summary=report.challenge_summary,
            difficulty_estimate=report.difficulty_estimate,
            confidence_score=confidence,
            skills_practiced=skills_practiced,
            learning_objectives=objectives,
            verification_section=verification_section,
            improvement_suggestions=suggestions,
        )

    @staticmethod
    def _format_instructor_summary(
        report: LearningReport,
        challenge_info: Optional[dict] = None,
        flag_result: Optional[dict] = None,
        tools_used: Optional[list[str]] = None,
    ) -> str:
        v = report.verification_result or {}
        confidence = v.get("confidence_score", 0.0) if isinstance(v, dict) else 0.0
        v_status = v.get("status", "unknown") if isinstance(v, dict) else "unknown"

        if confidence >= 0.8:
            perf = "Strong"
        elif confidence >= 0.5:
            perf = "Moderate"
        else:
            perf = "Needs Improvement"

        skills_detail = "\n".join(
            f"  - {s.get('name', 'unknown')} ({s.get('category', s.get('subdomain', 'uncategorised'))})"
            for s in report.skills_used
        ) if report.skills_used else "  (none)"

        mastered = "\n".join(
            f"  - {s}" for s in report.skills_mastered
        ) if report.skills_mastered else "  (none)"

        needing = "\n".join(
            f"  - {s}" for s in report.skills_needing_improvement
        ) if report.skills_needing_improvement else "  (none)"

        training = "\n".join(
            f"  - {r}" for r in report.recommendations
        ) if report.recommendations else "  (none)"

        if challenge_info:
            training += f"\n  Challenge Category: {challenge_info.get('category', 'unknown')}"
            training += f"\n  Challenge Difficulty: {challenge_info.get('difficulty', 'unknown')}"

        if flag_result:
            training += f"\n  Flag Verification: {flag_result.get('status', 'UNKNOWN')}"

        if tools_used:
            training += f"\n  Tools Selected: {', '.join(tools_used)}"

        return INSTRUCTOR_SUMMARY_TEMPLATE.format(
            challenge_id=report.challenge_id,
            challenge_summary=report.challenge_summary,
            difficulty_estimate=report.difficulty_estimate,
            performance_label=perf,
            skills_used_count=len(report.skills_used),
            skills_used_detail=skills_detail,
            skills_mastered=mastered,
            skills_needing_improvement=needing,
            verification_status=v_status,
            confidence_score=confidence,
            training_recommendations=training,
        )
