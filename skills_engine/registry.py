from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("skills_engine.registry")


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, dict] = {}
        self._by_subdomain: dict[str, list[str]] = {}
        self._by_tag: dict[str, list[str]] = {}
        self._by_category: dict[str, list[str]] = {}
        self._index: dict = {}

    def register(self, skill: dict) -> None:
        name = skill["frontmatter"].get("name", "")
        if not name:
            logger.warning("Attempted to register skill without a name")
            return
        if name in self._skills:
            logger.warning("Overwriting existing skill: %s", name)

        self._skills[name] = skill
        fm = skill["frontmatter"]

        subdomain = fm.get("subdomain", "general")
        self._by_subdomain.setdefault(subdomain, []).append(name)

        category = fm.get("category", subdomain)
        self._by_category.setdefault(category, []).append(name)

        for tag in fm.get("tags", []):
            self._by_tag.setdefault(tag, []).append(name)

        logger.debug("Registered skill: %s (subdomain=%s, category=%s)", name, subdomain, category)

    def register_many(self, skills: list[dict]) -> None:
        for skill in skills:
            self.register(skill)

    def set_index(self, index: dict) -> None:
        self._index = index

    def get(self, name: str) -> Optional[dict]:
        return self._skills.get(name)

    def get_frontmatter(self, name: str) -> Optional[dict]:
        skill = self._skills.get(name)
        if skill:
            return skill.get("frontmatter")
        return None

    def list(self) -> dict[str, str]:
        return {name: skill["frontmatter"].get("description", "")
                for name, skill in self._skills.items()}

    def list_names(self) -> list[str]:
        return list(self._skills.keys())

    def search(self, query: str) -> list[dict]:
        query = query.lower()
        terms = [t for t in query.split() if t]
        results = []
        for name, skill in self._skills.items():
            fm = skill["frontmatter"]
            text = " ".join([
                name.lower(),
                fm.get("description", "").lower(),
                " ".join(fm.get("tags", [])),
                fm.get("subdomain", "").lower(),
            ])
            if any(t in text for t in terms):
                results.append({
                    "name": name,
                    "description": fm.get("description", ""),
                    "subdomain": fm.get("subdomain", ""),
                    "tags": fm.get("tags", []),
                    "score": self._score_match(query, name, fm),
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def get_by_subdomain(self, subdomain: str) -> list[dict]:
        names = self._by_subdomain.get(subdomain, [])
        return [self._skills[n] for n in names if n in self._skills]

    def get_by_category(self, category: str) -> list[dict]:
        names = self._by_category.get(category, [])
        return [self._skills[n] for n in names if n in self._skills]

    def get_by_tag(self, tag: str) -> list[dict]:
        names = self._by_tag.get(tag, [])
        return [self._skills[n] for n in names if n in self._skills]

    def get_categories(self) -> dict[str, int]:
        counts = {}
        for name, skill in self._skills.items():
            cat = skill["frontmatter"].get("category", "general")
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def get_user_invocable(self) -> list[dict]:
        return [
            {"name": n, "description": s["frontmatter"].get("description", ""),
             "argument_hint": s["frontmatter"].get("argument_hint", "")}
            for n, s in self._skills.items()
            if s["frontmatter"].get("user_invocable", False)
        ]

    def remove(self, name: str) -> None:
        if name not in self._skills:
            return
        fm = self._skills[name]["frontmatter"]
        sub = fm.get("subdomain", "general")
        if name in self._by_subdomain.get(sub, []):
            self._by_subdomain[sub].remove(name)
        for tag in fm.get("tags", []):
            if name in self._by_tag.get(tag, []):
                self._by_tag[tag].remove(name)
        del self._skills[name]

    def _score_match(self, query: str, name: str, fm: dict) -> float:
        score = 0.0
        if name.lower() == query:
            score += 10.0
        elif query in name.lower():
            score += 5.0
        if query in fm.get("description", "").lower():
            score += 3.0
        if query in " ".join(fm.get("tags", [])).lower():
            score += 2.0
        if query in fm.get("subdomain", "").lower():
            score += 2.0
        return score

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    def __iter__(self):
        return iter(self._skills.values())
