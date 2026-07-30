from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

import yaml

from skills_engine.schema import SkillFrontmatter, SkillMetadata

logger = logging.getLogger("skills_engine.loader")

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _parse_frontmatter(text: str) -> Optional[dict]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        raw = yaml.safe_load(match.group(1))
        if isinstance(raw, dict):
            return raw
        return None
    except yaml.YAMLError as e:
        logger.warning("YAML parse error: %s", e)
        return None


def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class SkillLoader:
    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)

    def discover(self) -> list[Path]:
        if not self.skills_dir.exists():
            logger.warning("Skills directory does not exist: %s", self.skills_dir)
            return []
        entries = sorted(
            p for p in self.skills_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".") and p.name != "__pycache__"
        )
        logger.info("Discovered %d skill directories in %s", len(entries), self.skills_dir)
        return entries

    def load_skill(self, path: Path) -> Optional[dict]:
        skill_file = path / "SKILL.md"
        if not skill_file.exists():
            logger.warning("Missing SKILL.md in %s", path)
            return None

        text = skill_file.read_text(encoding="utf-8")
        raw = _parse_frontmatter(text)
        if not raw:
            logger.warning("No valid frontmatter in %s", skill_file)
            return None

        raw["name"] = raw.get("name", path.name)
        content_hash = _hash_content(text)

        md_files = sorted(p for p in path.rglob("*.md") if p.is_file())
        total_lines = sum(len(p.read_text(encoding="utf-8").split("\n")) for p in md_files)

        metadata = SkillMetadata(
            path=str(path.relative_to(self.skills_dir.parent)),
            content_hash=content_hash,
            file_count=len(md_files),
            total_lines=total_lines,
        )

        return {
            "frontmatter": raw,
            "metadata": metadata,
            "raw_text": text,
            "directory": str(path),
        }

    def load_all(self) -> list[dict]:
        skills = []
        for path in self.discover():
            skill = self.load_skill(path)
            if skill:
                skills.append(skill)
        logger.info("Loaded %d skills", len(skills))
        return skills

    def build_index(self, skills: list[dict]) -> dict:
        entries = []
        for skill in skills:
            fm = skill["frontmatter"]
            entries.append({
                "name": fm.get("name", ""),
                "description": fm.get("description", ""),
                "domain": fm.get("domain", "ctf"),
                "subdomain": fm.get("subdomain", ""),
                "category": fm.get("category", ""),
                "tags": fm.get("tags", []),
                "version": fm.get("version", "1.0"),
                "user_invocable": fm.get("user_invocable", False),
                "path": skill["metadata"].path,
                "file_count": skill["metadata"].file_count,
                "total_lines": skill["metadata"].total_lines,
                "content_hash": skill["metadata"].content_hash,
                "requires": fm.get("requires", []),
            })

        return {
            "version": "1.0",
            "total_skills": len(entries),
            "skills": entries,
        }

    def write_index(self, index: dict):
        import json
        index_path = self.skills_dir / "index.json"
        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Wrote index with %d skills to %s", index["total_skills"], index_path)

    def load_all_and_index(self) -> dict:
        skills = self.load_all()
        index = self.build_index(skills)
        self.write_index(index)
        return index
