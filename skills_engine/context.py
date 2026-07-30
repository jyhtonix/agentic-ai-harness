"""
Skill Context Builder.

Purpose: Transforms selected skills into optimized agent context prompts.
Manages token budgets, deduplicates knowledge, and structures the output
for efficient LLM consumption.

The builder produces modular skill blocks that can be injected via the
existing SkillInjector, maintaining backward compatibility.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("skills_engine.context")

CONTEXT_TEMPLATE = """
<skill_context>
The following skill(s) are relevant to the current task:
{skill_blocks}
</skill_context>
"""

SKILL_HEADER = """
=== Skill: {name} ({category}) ===
Difficulty: {difficulty}
{metadata}
"""

KNOWLEDGE_SECTION = """
{heading}
{content}
"""

TOOLS_SECTION = """
Required Tools:
{tools}
"""

VERIFICATION_SECTION = """
Verification Methods:
{methods}
"""


class SkillContextBuilder:
    def __init__(self, budget: int = 2048, deduplicate: bool = True):
        self.budget = budget
        self.deduplicate = deduplicate

    def build_context(self, selected_skills: list[dict]) -> str:
        if not selected_skills:
            return ""

        blocks = []
        seen_content: set[str] = set()
        total_tokens = 0
        remaining = self.budget

        for skill in selected_skills:
            block = self._build_skill_block(skill)
            if self.deduplicate:
                dedup_key = self._dedup_key(skill.get("raw_text", ""))
                if dedup_key in seen_content:
                    continue
                seen_content.add(dedup_key)

            block_tokens = self._estimate_tokens(block)
            if block_tokens > remaining:
                truncated = self._truncate_block(block, remaining)
                blocks.append(truncated)
                total_tokens += remaining
                break

            blocks.append(block)
            total_tokens += block_tokens
            remaining -= block_tokens

        if not blocks:
            return ""

        context = CONTEXT_TEMPLATE.format(
            skill_blocks="\n".join(blocks),
        )

        logger.info(
            "Built context with %d skill block(s) (%d tokens, budget=%d)",
            len(blocks), total_tokens, self.budget,
        )
        return context

    def build_injectable_skills(self, selected_skills: list[dict]) -> list[dict]:
        if not selected_skills:
            return []

        output = []
        seen_content: set[str] = set()

        for skill in selected_skills:
            name = skill.get("name", "unknown")
            raw_text = self._build_combined_raw(skill)

            if self.deduplicate:
                dedup_key = self._dedup_key(raw_text)
                if dedup_key in seen_content:
                    continue
                seen_content.add(dedup_key)

            output.append({
                "name": name,
                "description": skill.get("description", ""),
                "subdomain": skill.get("category", ""),
                "category": skill.get("category", ""),
                "tags": skill.get("tags", []),
                "score": skill.get("score", 0.0),
                "requires": skill.get("requires", []),
                "allowed_tools": skill.get("allowed_tools", []),
                "token_estimate": self._estimate_tokens(raw_text),
                "raw_text": raw_text,
                "difficulty": skill.get("difficulty", ""),
                "supported_challenges": skill.get("supported_challenges", []),
                "verification_methods": skill.get("verification_methods", []),
            })

        return output

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_skill_block(self, skill: dict) -> str:
        name = skill.get("name", "unknown")
        category = skill.get("category", "general")
        difficulty = skill.get("difficulty", "unknown")
        description = skill.get("description", "")
        tags = skill.get("tags", [])
        raw = skill.get("raw_text", "")

        metadata_parts = []
        if description:
            metadata_parts.append(f"Description: {description}")
        if tags:
            metadata_parts.append(f"Tags: {', '.join(tags[:8])}")

        header = SKILL_HEADER.format(
            name=name,
            category=category,
            difficulty=difficulty,
            metadata="\n".join(metadata_parts),
        )

        body = self._extract_knowledge(raw)
        tools = self._format_tools(skill)
        verification = self._format_verification(skill)

        parts = [header.strip()]
        if body:
            parts.append(KNOWLEDGE_SECTION.format(heading="Knowledge:", content=body).rstrip())
        if tools:
            parts.append(TOOLS_SECTION.format(tools=tools).rstrip())
        if verification:
            parts.append(VERIFICATION_SECTION.format(methods=verification).rstrip())

        return "\n".join(parts)

    @staticmethod
    def _build_combined_raw(skill: dict) -> str:
        parts = []
        name = skill.get("name", "unknown")
        desc = skill.get("description", "")
        difficulty = skill.get("difficulty", "")
        raw = skill.get("raw_text", "")

        parts.append(f"# {name}")
        if difficulty:
            parts.append(f"Difficulty: {difficulty}")
        parts.append("")
        if desc:
            parts.append(desc)
        if raw:
            parts.append("")
            parts.append(raw)

        return "\n".join(parts)

    @staticmethod
    def _extract_knowledge(raw_text: str) -> str:
        if not raw_text:
            return ""
        lines = raw_text.split("\n")
        knowledge_lines = []
        in_knowledge = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## Knowledge") or stripped.startswith("## Coverage"):
                in_knowledge = True
                continue
            if in_knowledge:
                if stripped.startswith("## ") and not stripped.startswith("###"):
                    break
                knowledge_lines.append(line)
        return "\n".join(knowledge_lines).strip()

    @staticmethod
    def _format_tools(skill: dict) -> str:
        tools = skill.get("allowed_tools", [])
        if not tools:
            return ""
        return "\n".join(f"- {t}" for t in tools)

    @staticmethod
    def _format_verification(skill: dict) -> str:
        methods = skill.get("verification_methods", [])
        if not methods:
            return ""
        return "\n".join(f"- {m}" for m in methods)

    @staticmethod
    def _dedup_key(block: str) -> str:
        return block.strip().lower()[:200]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 4

    def _truncate_block(self, block: str, target_tokens: int) -> str:
        target_chars = target_tokens * 4
        if len(block) <= target_chars:
            return block
        return block[:target_chars] + "\n\n[...truncated]"
