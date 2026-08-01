"""
Agent Skill Registry.

Purpose: Central, data-driven registry for specialist agent routing.
Each skill definition describes a specialist expert that the team
Coordinator can dispatch to. The registry replaces hardcoded routing
keywords as the single source of truth, while retaining an optional
fallback keyword map for backward compatibility.

Each skill defines:
    name          - unique skill identifier (e.g. "malware")
    category      - routing category, must match SpecialistAgent.category
    agent         - import path to the agent class "module:ClassName"
    prompt        - path to the expert prompt file (e.g. "prompts/malware_expert.md")
    keywords      - trigger keywords used for task classification
    capabilities  - capability identifiers advertised by the specialist
    version       - skill definition version
    enabled       - when False, the skill is excluded from routing

Usage:
    registry = SkillRegistry(fallback_keywords=CATEGORY_KEYWORDS)
    registry.register(SkillDefinition(name="devops", category="devops", ...))
    scores = registry.classify("Set up a Kubernetes deployment")
    registry.load_agent("devops")   # -> DevOpsAgent instance

    # Or load the full definition set from YAML:
    registry = load_skill_registry()

Clean architecture: The registry depends only on SpecialistAgent (for
typing) and knows nothing about concrete agent implementations. Agents
are instantiated lazily from their import path, avoiding import cycles.
"""

from __future__ import annotations

import importlib
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from agents.team.specialists import SpecialistAgent

logger = logging.getLogger("agents.team.skill_registry")

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "skills" / "agent_skills.yaml"


@dataclass
class SkillDefinition:
    """Definition of a specialist skill for routing and dispatch."""

    name: str
    category: str
    agent: str = ""
    prompt: str = ""
    keywords: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    version: str = "1.0"
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "agent": self.agent,
            "prompt": self.prompt,
            "keywords": list(self.keywords),
            "capabilities": list(self.capabilities),
            "version": self.version,
            "enabled": self.enabled,
        }


class SkillRegistry:
    """
    Registry of skill definitions keyed by category.

    Backward compatibility: when no definition exists for a category,
    keyword lookups fall back to the provided fallback_keywords map.
    """

    def __init__(self, fallback_keywords: Optional[dict[str, list[str]]] = None):
        self._skills: dict[str, SkillDefinition] = {}
        self._fallback_keywords: dict[str, list[str]] = dict(fallback_keywords or {})
        self._agent_cache: dict[str, "SpecialistAgent"] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, definition: SkillDefinition) -> None:
        if not definition or not definition.category:
            logger.warning("Refusing to register skill without a category")
            return
        existing = self._skills.get(definition.category)
        if existing:
            logger.warning("Overwriting existing skill definition: %s", definition.category)
        self._skills[definition.category] = definition
        self._agent_cache.pop(definition.category, None)
        logger.debug(
            "Registered skill '%s' (category=%s, keywords=%d, enabled=%s)",
            definition.name, definition.category, len(definition.keywords), definition.enabled,
        )

    def register_many(self, definitions: list[SkillDefinition]) -> None:
        for definition in definitions:
            self.register(definition)

    def register_agent(
        self,
        agent: "SpecialistAgent",
        keywords: Optional[list[str]] = None,
        prompt: Optional[str] = None,
    ) -> SkillDefinition:
        """
        Adopt a live specialist instance into the registry.

        When a definition already exists for the agent's category, its
        capabilities/agent path are refreshed while existing keywords
        are preserved (unless explicitly overridden).
        """
        category = agent.category
        import_path = f"{type(agent).__module__}:{type(agent).__name__}"

        existing = self._skills.get(category)
        if existing:
            existing.capabilities = list(agent.capabilities)
            if not existing.agent:
                existing.agent = import_path
            if keywords:
                existing.keywords = list(keywords)
            if prompt:
                existing.prompt = prompt
            self._agent_cache.pop(category, None)
            return existing

        definition = SkillDefinition(
            name=category,
            category=category,
            agent=import_path,
            prompt=prompt or f"prompts/{category}_expert.md",
            keywords=list(keywords) if keywords else list(self._fallback_keywords.get(category, [])),
            capabilities=list(agent.capabilities),
        )
        self.register(definition)
        return definition

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get(self, category: str) -> Optional[SkillDefinition]:
        return self._skills.get(category)

    def get_by_name(self, name: str) -> Optional[SkillDefinition]:
        for definition in self._skills.values():
            if definition.name == name:
                return definition
        return None

    def get_by_capability(self, capability: str) -> list[SkillDefinition]:
        return [
            definition for definition in self._skills.values()
            if capability in definition.capabilities
        ]

    def list_skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def list(self) -> dict[str, str]:
        """Return a dict of skill name -> category (registry-style view)."""
        return {s.name: s.category for s in self._skills.values()}

    def categories(self) -> list[str]:
        """All known routing categories: registered skills + fallback keys."""
        cats = set(self._fallback_keywords.keys())
        cats.update(self._skills.keys())
        return sorted(cats)

    def keywords_for(self, category: str) -> list[str]:
        """
        Keywords used to classify a category.

        Disabled skills contribute no keywords. Registered keywords take
        precedence; otherwise the fallback keyword map is used.
        """
        definition = self._skills.get(category)
        if definition:
            if not definition.enabled:
                return []
            if definition.keywords:
                return list(definition.keywords)
        return list(self._fallback_keywords.get(category, []))

    def set_enabled(self, category: str, enabled: bool) -> None:
        definition = self._skills.get(category)
        if definition:
            definition.enabled = enabled
            logger.info("Skill '%s' enabled=%s", category, enabled)

    def agent_path_for(self, category: str) -> str:
        definition = self._skills.get(category)
        return definition.agent if definition else ""

    # ------------------------------------------------------------------
    # Classification / routing
    # ------------------------------------------------------------------

    @staticmethod
    @lru_cache(maxsize=1024)
    def _keyword_pattern(keyword: str) -> "re.Pattern":
        """
        Compile a word-boundary-aware regex for a keyword.

        Word boundaries (`\\b`) prevent substring false positives:
        "elf" no longer matches "myself", but still matches "ELF binary".
        """
        return re.compile(rf"\b{re.escape(keyword)}\b")

    def classify(self, text: str) -> dict[str, float]:
        """
        Score a task against registered keyword sets.

        Mirrors the legacy CoordinatorAgent._classify algorithm: each
        keyword match contributes 2.0; scores are normalized to weights
        and sorted descending. Falls back to {"general": 1.0} when no
        category matches.

        Matching is word-boundary aware: a keyword matches only when it
        appears as a whole word (or phrase), not as a substring of a
        larger token. E.g. "elf" matches "ELF binary" but not "myself".
        """
        text = text.lower()

        scores: dict[str, float] = {}
        for category in self.categories():
            keywords = self.keywords_for(category)
            score = sum(
                2.0
                for kw in keywords
                if self._keyword_pattern(kw).search(text)
            )
            if score > 0:
                scores[category] = score

        if not scores:
            scores["general"] = 1.0

        total = sum(scores.values()) or 1
        return {
            cat: round(s / total, 2)
            for cat, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)
        }

    # ------------------------------------------------------------------
    # Agent instantiation
    # ------------------------------------------------------------------

    def load_agent(self, category: str, use_cache: bool = True) -> Optional["SpecialistAgent"]:
        """
        Instantiate the specialist agent for a category from its import
        path ("module:ClassName"). Returns None on failure.
        """
        if use_cache and category in self._agent_cache:
            return self._agent_cache[category]

        import_path = self.agent_path_for(category)
        module_path, sep, class_name = import_path.partition(":")
        if not sep or not class_name:
            logger.warning("No agent import path for category: %s", category)
            return None

        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            agent = cls()
        except (ImportError, AttributeError, TypeError) as exc:
            logger.error("Failed to load agent '%s' from '%s': %s", category, import_path, exc)
            return None

        if use_cache:
            self._agent_cache[category] = agent
        return agent


def load_skill_registry(
    path: Optional[str | Path] = None,
    fallback_keywords: Optional[dict[str, list[str]]] = None,
) -> SkillRegistry:
    """
    Build a SkillRegistry from the central YAML definition file.

    When the YAML file is missing, an empty registry (plus any fallback
    keywords) is returned so callers degrade gracefully.
    """
    registry = SkillRegistry(fallback_keywords=fallback_keywords)

    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not registry_path.exists():
        logger.warning("Skill registry file not found: %s", registry_path)
        return registry

    import yaml

    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.error("Failed to parse skill registry %s: %s", registry_path, exc)
        return registry

    entries = data.get("skills", [])
    for entry in entries:
        registry.register(SkillDefinition(**entry))

    logger.info("Loaded %d skill definition(s) from %s", len(entries), registry_path)
    return registry
