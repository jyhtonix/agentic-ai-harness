"""
Skill Pack Loader.

Purpose: Discovers, validates, and loads skill packs from the skill_packs/
directory. Each skill pack is a sub-directory containing:

  skill.yaml        — metadata (name, description, category, difficulty, etc.)
  README.md         — human-readable overview
  knowledge.md      — domain-specific knowledge content
  tools.yaml        — tool descriptions and usage
  prompts/          — optional prompt templates

The loader produces dicts compatible with SkillRegistry.register().
Invalid skill packs are logged and skipped — never crash the agent.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("skills_engine.pack_loader")

REQUIRED_FIELDS = ["name", "description", "category"]
OPTIONAL_FIELDS = [
    "difficulty", "supported_challenges", "required_tools",
    "verification_methods", "tags",
]


def _load_yaml(path: Path) -> Optional[dict]:
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
        logger.warning("YAML file %s is not a dict", path)
        return None
    except yaml.YAMLError as e:
        logger.warning("YAML parse error in %s: %s", path, e)
        return None
    except OSError as e:
        logger.warning("Cannot read %s: %s", path, e)
        return None


class SkillPackLoader:
    def __init__(self, packs_dir: str | Path = "skill_packs"):
        self.packs_dir = Path(packs_dir)

    def discover(self) -> list[Path]:
        if not self.packs_dir.exists():
            logger.info("Skill packs directory does not exist: %s", self.packs_dir)
            return []
        entries = sorted(
            p for p in self.packs_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".") and p.name != "__pycache__"
        )
        logger.info("Discovered %d skill pack directories", len(entries))
        return entries

    def load_pack(self, path: Path) -> Optional[dict]:
        skill_file = path / "skill.yaml"
        if not skill_file.exists():
            logger.warning("Missing skill.yaml in %s", path)
            return None

        raw = _load_yaml(skill_file)
        if not raw:
            logger.warning("Invalid skill.yaml in %s", path)
            return None

        errors = self._validate_required(raw, path)
        if errors:
            for err in errors:
                logger.warning("Validation error in %s: %s", path, err)
            return None

        name = raw.get("name", path.name)
        description = raw.get("description", "")
        category = raw.get("category", "general")
        tags = raw.get("tags", [])
        difficulty = raw.get("difficulty", "beginner")

        knowledge_text = self._load_text_file(path / "knowledge.md")
        readme_text = self._load_text_file(path / "README.md")
        tools_text = _load_yaml(path / "tools.yaml")
        prompts = self._load_prompts(path / "prompts")

        combined_text = self._build_combined_text(
            name, description, knowledge_text, readme_text, tools_text,
        )

        frontmatter = {
            "name": name,
            "description": description,
            "domain": "ctf",
            "subdomain": category,
            "category": category,
            "tags": tags if tags else ["ctf", category],
            "version": "1.0",
            "difficulty": difficulty,
            "supported_challenges": raw.get("supported_challenges", []),
            "required_tools": raw.get("required_tools", []),
            "verification_methods": raw.get("verification_methods", []),
            "allowed_tools": raw.get("required_tools", []),
            "requires": [],
            "user_invocable": False,
            "author": "agent-harness",
            "token_budget": {"frontmatter": 200, "full_content": 2000},
        }

        return {
            "frontmatter": frontmatter,
            "metadata": {
                "path": str(path.relative_to(self.packs_dir.parent)),
                "content_hash": "",
                "file_count": self._count_files(path),
                "total_lines": self._count_lines(path),
                "pack_format": True,
            },
            "raw_text": combined_text,
            "directory": str(path),
            "pack_data": {
                "difficulty": difficulty,
                "knowledge": knowledge_text,
                "tools": tools_text,
                "prompts": prompts,
                "verification_methods": raw.get("verification_methods", []),
            },
        }

    def load_all(self) -> list[dict]:
        packs = []
        for path in self.discover():
            pack = self.load_pack(path)
            if pack:
                packs.append(pack)
        logger.info("Loaded %d skill packs", len(packs))
        return packs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_required(raw: dict, path: Path) -> list[str]:
        errors = []
        for field in REQUIRED_FIELDS:
            if field not in raw or not raw.get(field):
                errors.append(f"missing required field '{field}'")
        return errors

    @staticmethod
    def _load_text_file(path: Path) -> str:
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                pass
        return ""

    @staticmethod
    def _load_prompts(prompts_dir: Path) -> list[dict]:
        if not prompts_dir.exists() or not prompts_dir.is_dir():
            return []
        prompts = []
        for f in sorted(prompts_dir.iterdir()):
            if f.suffix in (".md", ".txt", ".yaml", ".yml"):
                try:
                    content = f.read_text(encoding="utf-8")
                    prompts.append({"name": f.stem, "content": content, "file": f.name})
                except OSError:
                    pass
        return prompts

    @staticmethod
    def _build_combined_text(
        name: str,
        description: str,
        knowledge: str,
        readme: str,
        tools: Optional[dict],
    ) -> str:
        parts = [f"# {name}\n\n{description}"]
        if readme:
            parts.append(f"\n\n## Overview\n\n{readme}")
        if knowledge:
            parts.append(f"\n\n## Knowledge\n\n{knowledge}")
        if tools:
            tool_list = tools.get("tools", [])
            if tool_list:
                parts.append("\n\n## Tools\n")
                for t in tool_list:
                    t_name = t.get("name", "unknown")
                    t_desc = t.get("description", "")
                    parts.append(f"- {t_name}: {t_desc}")
        return "\n".join(parts)

    @staticmethod
    def _count_files(path: Path) -> int:
        count = 0
        for f in path.rglob("*"):
            if f.is_file():
                count += 1
        return count

    @staticmethod
    def _count_lines(path: Path) -> int:
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += len(f.read_text(encoding="utf-8").split("\n"))
                except OSError:
                    pass
        return total
