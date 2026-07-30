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
        category: str = "",
        difficulty: str = "",
        feedback: Optional[list[dict]] = None,
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

            filter_score = self._apply_filters(fm, category, difficulty, feedback)
            if filter_score == 0.0:
                continue

            adjusted_score = score * filter_score

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
                "score": round(adjusted_score, 3),
                "requires": fm.get("requires", []),
                "allowed_tools": fm.get("allowed_tools", []),
                "token_estimate": estimate,
                "raw_text": skill.get("raw_text", ""),
                "difficulty": fm.get("difficulty", ""),
                "supported_challenges": fm.get("supported_challenges", []),
                "verification_methods": fm.get("verification_methods", []),
            })
            token_total += estimate

        selected.sort(key=lambda x: x["score"], reverse=True)

        logger.info(
            "Selected %d skills for '%s' (budget=%d, used=%d, category=%s, difficulty=%s)",
            len(selected), agent_name or task_context[:40], budget, token_total,
            category or "any", difficulty or "any",
        )
        return selected[:limit]

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
            "difficulty": fm.get("difficulty", ""),
        }

    @staticmethod
    def _apply_filters(
        fm: dict,
        category: str,
        difficulty: str,
        feedback: Optional[list[dict]],
    ) -> float:
        score = 1.0

        if category:
            skill_cat = fm.get("category", "").lower()
            skill_sub = fm.get("subdomain", "").lower()
            cat_lower = category.lower()
            if cat_lower not in skill_cat and cat_lower not in skill_sub:
                return 0.0
            score *= 1.5

        if difficulty:
            skill_diff = fm.get("difficulty", "").lower()
            diff_lower = difficulty.lower()
            if skill_diff == diff_lower:
                score *= 1.3
            elif skill_diff == "beginner" and diff_lower == "intermediate":
                score *= 0.8
            elif skill_diff == "intermediate" and diff_lower == "advanced":
                score *= 0.8
            elif skill_diff == "advanced" and diff_lower == "intermediate":
                score *= 0.9
            elif skill_diff == "intermediate" and diff_lower == "beginner":
                score *= 0.7
            else:
                score *= 0.5

        if feedback:
            skill_name = fm.get("name", "")
            for entry in feedback:
                if isinstance(entry, dict) and entry.get("skill") == skill_name:
                    fb_score = entry.get("score", 0.0)
                    if fb_score > 0:
                        score *= (1.0 + fb_score * 0.1)
                    else:
                        score *= (1.0 + fb_score * 0.15)

        return max(0.1, score)
