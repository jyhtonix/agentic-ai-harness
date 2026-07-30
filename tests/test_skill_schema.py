"""Tests for the skill frontmatter schema models."""

from pydantic import ValidationError
import pytest
from skills_engine.schema import SkillFrontmatter, TokenBudget, FrameworkMapping, SkillMetadata


class TestSkillFrontmatter:
    def test_valid_minimal(self):
        fm = SkillFrontmatter(
            name="test-skill",
            description="A valid test skill for testing purposes.",
            subdomain="web",
        )
        assert fm.name == "test-skill"
        assert fm.domain == "ctf"
        assert fm.tags == ["ctf"]
        assert fm.version == "1.0"
        assert fm.license == "MIT"
        assert fm.user_invocable is False
        assert fm.category == "web"

    def test_valid_full(self):
        fm = SkillFrontmatter(
            name="full-skill",
            description="A comprehensive test skill with all fields populated.",
            domain="ctf",
            subdomain="crypto",
            category="crypto",
            tags=["crypto", "rsa", "aes"],
            version="2.1.0",
            author="test-author",
            license="MIT",
            frameworks=FrameworkMapping(
                mitre_attack=["T1190"],
                nist_csf=["DE.CM-01"],
            ),
            allowed_tools=["web_search", "code_runner"],
            requires=["ctf-web"],
            user_invocable=True,
            argument_hint="[ciphertext_file]",
            token_budget=TokenBudget(frontmatter=150, full_content=1200),
            metadata={"difficulty": "medium"},
        )
        assert fm.name == "full-skill"
        assert fm.frameworks.mitre_attack == ["T1190"]
        assert fm.allowed_tools == ["web_search", "code_runner"]
        assert fm.requires == ["ctf-web"]
        assert fm.user_invocable is True

    def test_auto_category_default(self):
        fm = SkillFrontmatter(
            name="auto-cat",
            description="Skill with auto category from subdomain.",
            subdomain="forensics",
        )
        assert fm.category == "forensics"

    def test_auto_argument_hint(self):
        fm = SkillFrontmatter(
            name="solve-me",
            description="A user-invocable solve skill.",
            subdomain="general",
            user_invocable=True,
        )
        assert fm.argument_hint == "[solve-me_task]"

    def test_invalid_name_pattern(self):
        with pytest.raises(ValidationError):
            SkillFrontmatter(
                name="Has Spaces",
                description="Invalid name should fail.",
                subdomain="web",
            )

    def test_invalid_name_empty(self):
        with pytest.raises(ValidationError):
            SkillFrontmatter(
                name="",
                description="Empty name should fail.",
                subdomain="web",
            )

    def test_invalid_description_too_short(self):
        with pytest.raises(ValidationError):
            SkillFrontmatter(
                name="short-desc",
                description="Too short",
                subdomain="web",
            )

    def test_invalid_version_format(self):
        with pytest.raises(ValidationError):
            SkillFrontmatter(
                name="bad-version",
                description="A skill with an invalid version format.",
                subdomain="web",
                version="abc",
            )


class TestTokenBudget:
    def test_defaults(self):
        tb = TokenBudget()
        assert tb.frontmatter == 200
        assert tb.full_content == 1500

    def test_custom(self):
        tb = TokenBudget(frontmatter=50, full_content=800)
        assert tb.frontmatter == 50
        assert tb.full_content == 800


class TestFrameworkMapping:
    def test_defaults(self):
        fm = FrameworkMapping()
        assert fm.mitre_attack == []
        assert fm.nist_csf == []
        assert fm.kill_chain == []

    def test_with_data(self):
        fm = FrameworkMapping(
            mitre_attack=["T1190", "T1505"],
            nist_csf=["DE.CM-01", "RS.MA-01"],
        )
        assert len(fm.mitre_attack) == 2
        assert len(fm.nist_csf) == 2


class TestSkillMetadata:
    def test_all_fields(self):
        sm = SkillMetadata(
            path="skills/test-skill",
            content_hash="abc123def456",
            file_count=3,
            total_lines=150,
            loaded_at="2026-07-30T20:00:00",
        )
        assert sm.path == "skills/test-skill"
        assert sm.content_hash == "abc123def456"
        assert sm.file_count == 3
        assert sm.total_lines == 150
