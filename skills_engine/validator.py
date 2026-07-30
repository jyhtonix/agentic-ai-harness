from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from skills_engine.schema import SkillFrontmatter, VALID_SUBDOMAINS, VALID_DOMAINS

logger = logging.getLogger("skills_engine.validator")


class ValidationResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.skill_name: str = ""

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict:
        return {
            "skill": self.skill_name,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class SkillValidator:
    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)
        self._known_skills: set[str] = set()
        self._known_tools: set[str] = set()

    def set_known_skills(self, names: set[str]) -> None:
        self._known_skills = names

    def set_known_tools(self, names: set[str]) -> None:
        self._known_tools = names

    def validate_frontmatter(self, raw: dict, skill_path: Path) -> ValidationResult:
        result = ValidationResult()
        result.skill_name = raw.get("name", skill_path.name)

        try:
            fm = SkillFrontmatter(**raw)
        except ValidationError as e:
            for err in e.errors():
                loc = " → ".join(str(x) for x in err["loc"])
                result.add_error(f"{loc}: {err['msg']}")
            fm = None

        if fm:
            name = fm.name
            if name != skill_path.name:
                result.add_warning(
                    f"frontmatter name '{name}' does not match directory name '{skill_path.name}'"
                )

            if fm.domain not in VALID_DOMAINS:
                result.add_warning(
                    f"domain '{fm.domain}' is not in standard set: {VALID_DOMAINS}"
                )

            if fm.subdomain not in VALID_SUBDOMAINS:
                result.add_warning(
                    f"subdomain '{fm.subdomain}' is not in standard set: {VALID_SUBDOMAINS}"
                )

            if fm.allowed_tools and self._known_tools:
                for tool in fm.allowed_tools:
                    if tool not in self._known_tools:
                        result.add_warning(f"allowed_tool '{tool}' is not in known tool set")

        if raw.get("license") and raw["license"] not in ("MIT", "Apache-2.0", "CC-BY-4.0"):
            result.add_warning(f"unusual license: {raw['license']}")

        return result

    def validate_cross_references(self, raw: dict, skill_path: Path) -> ValidationResult:
        result = ValidationResult()
        result.skill_name = raw.get("name", skill_path.name)

        requires = raw.get("requires", [])
        if isinstance(requires, list):
            for req in requires:
                if req not in self._known_skills:
                    if not (self.skills_dir / req).exists():
                        result.add_error(
                            f"requires '{req}' does not match any known skill path"
                        )

        skill_file = skill_path / "SKILL.md" if skill_path.is_dir() else skill_path
        text = skill_file.read_text(encoding="utf-8") if skill_file.exists() else ""
        refs = set()
        import re
        for m in re.finditer(r"/ctf-([a-z0-9-]+)", text):
            refs.add(m.group(0))
        for ref in refs:
            ref_clean = ref.lstrip("/")
            if ref_clean not in self._known_skills:
                result.add_warning(f"cross-reference '{ref}' does not match a known skill")

        return result

    def validate_skill_directory(self, name: str) -> ValidationResult:
        result = ValidationResult()
        result.skill_name = name
        skill_path = self.skills_dir / name
        if not skill_path.exists():
            result.add_error(f"skill directory '{name}' does not exist")
            return result
        skill_file = skill_path / "SKILL.md"
        if not skill_file.exists():
            result.add_error(f"missing SKILL.md in '{name}'")
            return result
        return result

    def validate_all(self, skills: list[dict]) -> list[ValidationResult]:
        results = []
        for skill in skills:
            fm = skill["frontmatter"]
            path = Path(skill["directory"])
            r1 = self.validate_frontmatter(fm, path)
            r2 = self.validate_cross_references(fm, path)
            combined = ValidationResult()
            combined.skill_name = r1.skill_name
            combined.errors = r1.errors + r2.errors
            combined.warnings = r1.warnings + r2.warnings
            if combined.passed and not combined.warnings:
                logger.info("✓ %s passed validation", combined.skill_name)
            elif combined.passed:
                logger.info("~ %s passed with warnings", combined.skill_name)
            else:
                logger.warning("✗ %s failed validation", combined.skill_name)
            results.append(combined)
        return results
