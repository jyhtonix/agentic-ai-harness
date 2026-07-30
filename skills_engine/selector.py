from __future__ import annotations

import logging
from typing import Optional

from skills_engine.registry import SkillRegistry

logger = logging.getLogger("skills_engine.selector")


class SkillSelector:
    def __init__(self, registry: SkillRegistry, memory_manager=None):
        self.registry = registry
        self.memory_manager = memory_manager

    async def select(
        self,
        task_context: str,
        agent_name: str = "",
        limit: int = 3,
        budget: int = 2048,
    ) -> list[dict]:
        candidates = []
        seen = set()

        if self.memory_manager:
            semantic = await self.memory_manager.search_skills(task_context, limit=limit * 2)
            for hit in semantic:
                name = hit.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    skill = self.registry.get(name)
                    if skill:
                        candidates.append((hit["score"], skill))

        if not candidates:
            results = self.registry.search(task_context)
            for r in results:
                name = r.get("name", "")
                if name not in seen:
                    seen.add(name)
                    skill = self.registry.get(name)
                    if skill:
                        candidates.append((r.get("score", 0), skill))

        candidates.sort(key=lambda x: x[0], reverse=True)

        selected = []
        token_total = 0

        for score, skill in candidates:
            fm = skill.get("frontmatter", {})
            tb = fm.get("token_budget", {})

            full_estimate = tb.get("full_content", 1500) if isinstance(tb, dict) else 1500
            front_estimate = tb.get("frontmatter", 200) if isinstance(tb, dict) else 200
            estimate = front_estimate + full_estimate

            if token_total + estimate > budget and selected:
                continue

            selected.append({
                "name": fm.get("name", ""),
                "description": fm.get("description", ""),
                "subdomain": fm.get("subdomain", ""),
                "tags": fm.get("tags", []),
                "category": fm.get("category", ""),
                "score": round(score, 3),
                "requires": fm.get("requires", []),
                "allowed_tools": fm.get("allowed_tools", []),
                "token_estimate": estimate,
                "raw_text": skill.get("raw_text", ""),
            })
            token_total += estimate

        logger.info(
            "Selected %d skills for '%s' (budget=%d, used=%d)",
            len(selected), agent_name or task_context[:40], budget, token_total,
        )
        return selected

    async def select_by_name(self, name: str) -> Optional[dict]:
        skill = self.registry.get(name)
        if not skill:
            return None
        fm = skill.get("frontmatter", {})
        return {
            "name": fm.get("name", ""),
            "description": fm.get("description", ""),
            "subdomain": fm.get("subdomain", ""),
            "tags": fm.get("tags", []),
            "category": fm.get("category", ""),
            "requires": fm.get("requires", []),
            "allowed_tools": fm.get("allowed_tools", []),
            "raw_text": skill.get("raw_text", ""),
        }
