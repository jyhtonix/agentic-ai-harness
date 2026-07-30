"""Tests for the SkillValidator."""

import tempfile
from pathlib import Path

import pytest
from skills_engine.validator import SkillValidator, ValidationResult
from skills_engine.schema import SkillFrontmatter


GOOD_FRONTMATTER = {
    "name": "valid-skill",
    "description": "A valid skill for testing validation logic.",
    "domain": "ctf",
    "subdomain": "web",
    "category": "web",
    "tags": ["web", "sqli"],
    "version": "1.0",
    "license": "MIT",
    "requires": [],
}

GOOD_SKILL_MD = """---
name: valid-skill
description: A valid skill for testing validation logic.
domain: ctf
subdomain: web
category: web
tags: [web, sqli]
version: "1.0"
license: "MIT"
requires: []
---

Valid content here.
"""


class TestValidationResult:
    def test_passed_when_no_errors(self):
        r = ValidationResult()
        assert r.passed is True

    def test_failed_when_errors_exist(self):
        r = ValidationResult()
        r.add_error("something wrong")
        assert r.passed is False

    def test_to_dict(self):
        r = ValidationResult()
        r.skill_name = "test"
        r.add_error("err1")
        r.add_warning("warn1")
        d = r.to_dict()
        assert d["skill"] == "test"
        assert d["passed"] is False
        assert "err1" in d["errors"]
        assert "warn1" in d["warnings"]


class TestSkillValidator:
    @pytest.fixture
    def validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = SkillValidator(tmp)
            yield v

    def test_validate_frontmatter_valid(self, validator):
        result = validator.validate_frontmatter(GOOD_FRONTMATTER, Path("valid-skill"))
        assert result.passed is True

    def test_validate_frontmatter_missing_name(self, validator):
        result = validator.validate_frontmatter(
            {"description": "No name field here at all.", "subdomain": "web"},
            Path("unnamed"),
        )
        assert result.passed is False

    def test_validate_frontmatter_warns_unusual_license(self, validator):
        result = validator.validate_frontmatter(
            {**GOOD_FRONTMATTER, "license": "GPL-3.0"},
            Path("valid-skill"),
        )
        assert result.passed is True
        assert any("unusual license" in w for w in result.warnings)

    def test_validate_frontmatter_warns_name_dir_mismatch(self, validator):
        result = validator.validate_frontmatter(
            GOOD_FRONTMATTER,
            Path("different-dir-name"),
        )
        assert result.passed is True
        assert any("does not match directory name" in w for w in result.warnings)

    def test_validate_frontmatter_warns_unknown_subdomain(self, validator):
        result = validator.validate_frontmatter(
            {**GOOD_FRONTMATTER, "subdomain": "quantum-hacking"},
            Path("valid-skill"),
        )
        assert result.passed is True
        assert any("subdomain" in w for w in result.warnings)

    def test_validate_frontmatter_warns_unknown_tool(self, validator):
        v = SkillValidator("skills")
        v.set_known_tools({"web_search", "code_runner"})
        result = v.validate_frontmatter(
            {**GOOD_FRONTMATTER, "allowed_tools": ["nonexistent_tool"]},
            Path("valid-skill"),
        )
        assert result.passed is True
        assert any("allowed_tool" in w for w in result.warnings)

    def test_validate_cross_references_known_skills(self, validator):
        validator.set_known_skills({"ctf-web", "ctf-forensics"})
        result = validator.validate_cross_references(
            {"name": "test", "requires": ["ctf-web"]},
            Path("test"),
        )
        assert result.passed is True

    def test_validate_cross_references_unknown_skill(self, validator):
        validator.set_known_skills({"ctf-web"})
        skill_file = Path(validator.skills_dir) / "test" / "SKILL.md"
        (Path(validator.skills_dir) / "test").mkdir(parents=True, exist_ok=True)
        skill_file.write_text("---\nname: test\n---")

        result = validator.validate_cross_references(
            {"name": "test", "requires": ["nonexistent-skill"]},
            Path(validator.skills_dir) / "test",
        )
        assert result.passed is False
        assert any("nonexistent-skill" in e for e in result.errors)

    def test_validate_skill_directory_missing(self, validator):
        result = validator.validate_skill_directory("ghost")
        assert result.passed is False
        assert any("does not exist" in e for e in result.errors)

    def test_validate_skill_directory_missing_skilmd(self, validator):
        (Path(validator.skills_dir) / "empty").mkdir()
        result = validator.validate_skill_directory("empty")
        assert result.passed is False
        assert any("missing SKILL.md" in e for e in result.errors)

    def test_validate_skill_directory_ok(self, validator):
        d = Path(validator.skills_dir) / "ok-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(GOOD_SKILL_MD)
        result = validator.validate_skill_directory("ok-skill")
        assert result.passed is True

    def test_validate_all_skills(self, validator):
        from skills_engine.loader import SkillLoader
        for name in ["alpha", "beta"]:
            d = Path(validator.skills_dir) / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                GOOD_SKILL_MD.replace("valid-skill", name)
            )
        loader = SkillLoader(validator.skills_dir)
        skills = loader.load_all()
        validator.set_known_skills({"alpha", "beta"})
        results = validator.validate_all(skills)
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_set_known_tools(self, validator):
        validator.set_known_tools({"tool_a", "tool_b"})
        # no crash
