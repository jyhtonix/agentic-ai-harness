from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("skills_engine.injector")


INJECTION_TEMPLATE = """
<skill_context>
The following skill(s) are relevant to the current task:

{skill_blocks}
</skill_context>
"""

SKILL_BLOCK_TEMPLATE = """
=== Skill: {name} ({subdomain}) ===
{content}
"""


class SkillInjector:
    def __init__(self, budget: int = 2048):
        self.budget = budget
        self._injection_cache: dict[str, int] = {}

    def inject(self, base_prompt: str, selected_skills: list[dict]) -> str:
        if not selected_skills:
            return base_prompt

        blocks = []
        total_skill_tokens = 0
        remaining = self.budget

        for sk in selected_skills:
            raw = sk.get("raw_text", "")
            if not raw:
                continue

            content = SKILL_BLOCK_TEMPLATE.format(
                name=sk.get("name", "unknown"),
                subdomain=sk.get("subdomain", ""),
                content=raw,
            )

            content_tokens = self._estimate_tokens(content)
            if content_tokens > remaining:
                truncated = self._truncate(raw, remaining)
                content = SKILL_BLOCK_TEMPLATE.format(
                    name=sk.get("name", "unknown"),
                    subdomain=sk.get("subdomain", ""),
                    content=truncated,
                )
                blocks.append(content)
                total_skill_tokens += remaining
                break

            blocks.append(content)
            total_skill_tokens += content_tokens
            remaining -= content_tokens

        if not blocks:
            return base_prompt

        context_block = INJECTION_TEMPLATE.format(
            skill_blocks="\n".join(blocks),
        )

        logger.info(
            "Injected %d skill(s) (%d tokens) into prompt",
            len(selected_skills), total_skill_tokens,
        )
        return base_prompt + context_block

    def inject_into_messages(self, messages: list[dict], selected_skills: list[dict]) -> list[dict]:
        if not selected_skills:
            return messages

        inserted = False
        new_messages = []

        for msg in messages:
            if msg["role"] == "system" and not inserted:
                enriched = self.inject(msg["content"], selected_skills)
                new_messages.append({"role": "system", "content": enriched})
                inserted = True
            else:
                new_messages.append(msg)

        if not inserted:
            context = INJECTION_TEMPLATE.format(
                skill_blocks="\n".join(
                    SKILL_BLOCK_TEMPLATE.format(
                        name=s.get("name", "unknown"),
                        subdomain=s.get("subdomain", ""),
                        content=s.get("raw_text", ""),
                    )
                    for s in selected_skills if s.get("raw_text")
                ),
            )
            new_messages.insert(0, {"role": "system", "content": context})

        return new_messages

    def enrich_system_prompt(self, system_prompt: str, selected_skills: list[dict]) -> str:
        return self.inject(system_prompt, selected_skills)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 4

    @staticmethod
    def _truncate(text: str, target_tokens: int) -> str:
        target_chars = target_tokens * 4
        if len(text) <= target_chars:
            return text
        return text[:target_chars] + "\n\n[...truncated]"
