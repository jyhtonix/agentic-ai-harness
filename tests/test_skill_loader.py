"""Tests for the SkillLoader."""

import json
import tempfile
from pathlib import Path

import pytest
from skills_engine.loader import SkillLoader, _parse_frontmatter


SAMPLE_SKILL_MD = """---
name: test-skill
description: A test skill for unit testing purposes with sufficient length.
domain: ctf
subdomain: web
category: web
tags: [web, sqli]
version: "1.0"
author: "test"
license: "MIT"
allowed-tools: [web_search]
requires: []
user_invocable: false
---

## When to Use

Test content for validation.
"""

SAMPLE_NO_FRONTMATTER = """# Just a regular markdown file

No YAML frontmatter here.
"""


class TestParseFrontmatter:
    def test_parses_valid_frontmatter(self):
        result = _parse_frontmatter(SAMPLE_SKILL_MD)
        assert result is not None
        assert result["name"] == "test-skill"
        assert result["subdomain"] == "web"
        assert result["tags"] == ["web", "sqli"]

    def test_returns_none_for_no_frontmatter(self):
        result = _parse_frontmatter(SAMPLE_NO_FRONTMATTER)
        assert result is None

    def test_returns_none_for_empty_content(self):
        result = _parse_frontmatter("")
        assert result is None

    def test_handles_partial_frontmatter(self):
        result = _parse_frontmatter("---\nname: partial\n---")
        assert result is not None
        assert result.get("name") == "partial"


class TestSkillLoader:
    @pytest.fixture
    def temp_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills_dir = Path(tmp) / "skills"
            skills_dir.mkdir()
            yield skills_dir

    def test_discover_empty_directory(self, temp_skills_dir):
        loader = SkillLoader(temp_skills_dir)
        entries = loader.discover()
        assert entries == []

    def test_discover_finds_directories(self, temp_skills_dir):
        (temp_skills_dir / "test-skill").mkdir()
        (temp_skills_dir / "another-skill").mkdir()
        loader = SkillLoader(temp_skills_dir)
        entries = loader.discover()
        assert len(entries) == 2

    def test_discover_ignores_files(self, temp_skills_dir):
        (temp_skills_dir / "index.json").write_text("{}")
        (temp_skills_dir / "test-skill").mkdir()
        loader = SkillLoader(temp_skills_dir)
        entries = loader.discover()
        assert len(entries) == 1

    def test_load_skill(self, temp_skills_dir):
        skill_dir = temp_skills_dir / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(SAMPLE_SKILL_MD)
        loader = SkillLoader(temp_skills_dir)
        result = loader.load_skill(skill_dir)
        assert result is not None
        assert result["frontmatter"]["name"] == "test-skill"
        assert result["metadata"].file_count == 1
        assert result["metadata"].content_hash is not None

    def test_load_skill_missing_skilmd(self, temp_skills_dir):
        skill_dir = temp_skills_dir / "empty-skill"
        skill_dir.mkdir()
        loader = SkillLoader(temp_skills_dir)
        result = loader.load_skill(skill_dir)
        assert result is None

    def test_load_skill_no_frontmatter(self, temp_skills_dir):
        skill_dir = temp_skills_dir / "no-fm"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(SAMPLE_NO_FRONTMATTER)
        loader = SkillLoader(temp_skills_dir)
        result = loader.load_skill(skill_dir)
        assert result is None

    def test_load_all(self, temp_skills_dir):
        for name in ["skill-a", "skill-b"]:
            d = temp_skills_dir / name
            d.mkdir()
            (d / "SKILL.md").write_text(SAMPLE_SKILL_MD.replace("test-skill", name))

        loader = SkillLoader(temp_skills_dir)
        skills = loader.load_all()
        assert len(skills) == 2

    def test_build_index(self, temp_skills_dir):
        d = temp_skills_dir / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(SAMPLE_SKILL_MD.replace("test-skill", "my-skill"))

        loader = SkillLoader(temp_skills_dir)
        skills = loader.load_all()
        index = loader.build_index(skills)
        assert index["version"] == "1.0"
        assert index["total_skills"] == 1
        assert index["skills"][0]["name"] == "my-skill"
        assert "content_hash" in index["skills"][0]

    def test_write_index(self, temp_skills_dir):
        d = temp_skills_dir / "write-test"
        d.mkdir()
        (d / "SKILL.md").write_text(SAMPLE_SKILL_MD.replace("test-skill", "write-test"))

        loader = SkillLoader(temp_skills_dir)
        skills = loader.load_all()
        index = loader.build_index(skills)
        loader.write_index(index)

        index_file = temp_skills_dir / "index.json"
        assert index_file.exists()
        loaded = json.loads(index_file.read_text())
        assert loaded["total_skills"] == 1

    def test_load_all_and_index(self, temp_skills_dir):
        for name in ["aa", "bb"]:
            d = temp_skills_dir / name
            d.mkdir()
            (d / "SKILL.md").write_text(SAMPLE_SKILL_MD.replace("test-skill", name))

        loader = SkillLoader(temp_skills_dir)
        index = loader.load_all_and_index()
        assert index["total_skills"] == 2
        assert (temp_skills_dir / "index.json").exists()


class TestRealSkills:
    def test_loads_production_skills(self):
        loader = SkillLoader("skills")
        skills = loader.load_all()
        assert len(skills) >= 4
        names = {s["frontmatter"]["name"] for s in skills}
        assert "solve-challenge" in names
        assert "ctf-web" in names
        assert "ctf-forensics" in names
