import logging
from typing import Optional

from tools.execution.registry import ToolDefinition

logger = logging.getLogger("tools.execution.selector")


class ToolSelector:
    def __init__(self, registry):
        self.registry = registry

    async def select(
        self,
        challenge_description: str,
        selected_skills: Optional[list[dict]] = None,
        required_capability: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        query = (challenge_description or "").lower()
        candidates = self.registry.get_tools(category=category) if category else list(self.registry)

        scored = []
        for tool in candidates:
            score = self._score_tool(tool, query, required_capability, selected_skills)
            if score > 0.0:
                scored.append((score, tool))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        results = []
        for score, tool in top:
            entry = tool.to_dict()
            entry["confidence"] = round(score, 2)
            results.append(entry)

        return results

    def _score_tool(self, tool: ToolDefinition, query: str,
                    required_capability: Optional[str] = None,
                    selected_skills: Optional[list[dict]] = None) -> float:
        score = 0.0
        query_words = set(query.split())

        name_lower = tool.name.lower()
        desc_lower = tool.description.lower()
        purpose_lower = tool.purpose.lower()
        combined = f"{name_lower} {desc_lower} {purpose_lower}"

        for word in query_words:
            if len(word) < 3:
                continue
            if word in combined:
                score += 0.3

        if required_capability:
            cap_lower = required_capability.lower()
            if cap_lower in combined:
                score += 0.5

        if selected_skills:
            skill_text = " ".join(
                s.get("name", "") + " " + s.get("description", "") + " "
                + " ".join(s.get("tags", []))
                for s in selected_skills
            ).lower()
            for word in query_words:
                if len(word) >= 3 and word in skill_text:
                    score += 0.1

        if score == 0.0 and not query.strip():
            score = 0.1

        return score
