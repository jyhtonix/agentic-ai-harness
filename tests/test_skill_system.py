"""Tests for the Skill Pack system: discovery, loading, selection, and context building.

Tests cover:
  - SkillPackLoader: discovery, validation, load, error handling
  - SkillSelector enhancement: category/difficulty/feedback filters
  - SkillContextBuilder: context generation, deduplication, token budget
  - Integration: full flow from pack loading to context injection

All tests use the skill_packs/ test fixtures and mock data — no external deps.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from skills_engine.pack_loader import SkillPackLoader
from skills_engine.selector import SkillSelector
from skills_engine.context import SkillContextBuilder
from skills_engine.registry import SkillRegistry


# ---------------------------------------------------------------------------
# Fixtures: temporary skill pack directories for isolation
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_packs_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


def write_skill_yaml(pack_dir: Path, overrides: dict = None):
    data = {
        "name": pack_dir.name,
        "description": f"A test skill pack called {pack_dir.name}",
        "category": "test",
        "difficulty": "beginner",
        "supported_challenges": ["challenge-a"],
        "required_tools": ["tool1"],
        "verification_methods": ["verify step 1"],
        "tags": ["test", pack_dir.name],
    }
    if overrides:
        data.update(overrides)
    (pack_dir / "skill.yaml").write_text(yaml.dump(data), encoding="utf-8")


def write_readme(pack_dir: Path, content: str = None):
    if content is None:
        content = f"# {pack_dir.name}\n\nTest pack overview.\n"
    (pack_dir / "README.md").write_text(content, encoding="utf-8")


def write_knowledge(pack_dir: Path, content: str = None):
    if content is None:
        content = f"## Coverage\n\nTest knowledge for {pack_dir.name}.\n"
    (pack_dir / "knowledge.md").write_text(content, encoding="utf-8")


def create_valid_pack(packs_dir: Path, name: str, overrides: dict = None):
    d = packs_dir / name
    d.mkdir(parents=True, exist_ok=True)
    write_skill_yaml(d, overrides)
    write_readme(d)
    write_knowledge(d)
    return d


def make_registry_skill(name: str, category: str = "test",
                        difficulty: str = "beginner", tags: list[str] = None) -> dict:
    return {
        "frontmatter": {
            "name": name,
            "description": f"Skill for {name}",
            "domain": "ctf",
            "subdomain": category,
            "category": category,
            "tags": tags or ["ctf", category],
            "version": "1.0",
            "difficulty": difficulty,
            "supported_challenges": [],
            "verification_methods": [],
            "token_budget": {"frontmatter": 50, "full_content": 200},
            "allowed_tools": [],
            "requires": [],
        },
        "metadata": {"path": f"skills/{name}", "content_hash": "abc"},
        "raw_text": f"# {name}\n\nTest content.\n",
    }


# ===================================================================
# Task 2 — SkillPackLoader Tests
# ===================================================================

class TestSkillPackDiscovery:
    def test_discovers_valid_packs(self, tmp_packs_dir):
        create_valid_pack(tmp_packs_dir, "pack-a")
        create_valid_pack(tmp_packs_dir, "pack-b")
        loader = SkillPackLoader(tmp_packs_dir)
        dirs = loader.discover()
        names = sorted(d.name for d in dirs)
        assert names == ["pack-a", "pack-b"]

    def test_ignores_non_directories(self, tmp_packs_dir):
        (tmp_packs_dir / "not_a_pack.txt").write_text("hello")
        create_valid_pack(tmp_packs_dir, "valid-pack")
        loader = SkillPackLoader(tmp_packs_dir)
        dirs = loader.discover()
        assert all(d.is_dir() for d in dirs)
        names = [d.name for d in dirs]
        assert "valid-pack" in names
        assert "not_a_pack.txt" not in names

    def test_ignores_hidden_directories(self, tmp_packs_dir):
        (tmp_packs_dir / ".hidden").mkdir()
        create_valid_pack(tmp_packs_dir, "visible")
        loader = SkillPackLoader(tmp_packs_dir)
        dirs = loader.discover()
        names = [d.name for d in dirs]
        assert "visible" in names
        assert ".hidden" not in names

    def test_empty_directory_returns_empty(self, tmp_packs_dir):
        loader = SkillPackLoader(tmp_packs_dir)
        assert loader.discover() == []

    def test_nonexistent_directory_returns_empty(self):
        loader = SkillPackLoader("/nonexistent/path")
        assert loader.discover() == []


class TestSkillPackValidation:
    def test_loads_valid_pack(self, tmp_packs_dir):
        create_valid_pack(tmp_packs_dir, "valid-pack")
        loader = SkillPackLoader(tmp_packs_dir)
        result = loader.load_pack(tmp_packs_dir / "valid-pack")
        assert result is not None
        assert result["frontmatter"]["name"] == "valid-pack"
        assert result["frontmatter"]["category"] == "test"
        assert result["frontmatter"]["difficulty"] == "beginner"
        assert "test skill pack" in result["frontmatter"]["description"].lower()

    def test_rejects_missing_skill_yaml(self, tmp_packs_dir):
        d = tmp_packs_dir / "no-yaml"
        d.mkdir()
        (d / "README.md").write_text("# No yaml")
        loader = SkillPackLoader(tmp_packs_dir)
        assert loader.load_pack(d) is None

    def test_rejects_missing_required_name(self, tmp_packs_dir):
        d = tmp_packs_dir / "no-name"
        d.mkdir()
        write_skill_yaml(d, {"name": ""})
        loader = SkillPackLoader(tmp_packs_dir)
        assert loader.load_pack(d) is None

    def test_rejects_missing_required_description(self, tmp_packs_dir):
        d = tmp_packs_dir / "no-desc"
        d.mkdir()
        write_skill_yaml(d, {"description": ""})
        loader = SkillPackLoader(tmp_packs_dir)
        assert loader.load_pack(d) is None

    def test_rejects_missing_required_category(self, tmp_packs_dir):
        d = tmp_packs_dir / "no-cat"
        d.mkdir()
        write_skill_yaml(d, {"category": ""})
        loader = SkillPackLoader(tmp_packs_dir)
        assert loader.load_pack(d) is None

    def test_handles_malformed_yaml(self, tmp_packs_dir):
        d = tmp_packs_dir / "bad-yaml"
        d.mkdir()
        (d / "skill.yaml").write_text(": : invalid yaml ::")
        loader = SkillPackLoader(tmp_packs_dir)
        assert loader.load_pack(d) is None

    def test_handles_yaml_with_list_instead_of_dict(self, tmp_packs_dir):
        d = tmp_packs_dir / "list-yaml"
        d.mkdir()
        (d / "skill.yaml").write_text("- item1\n- item2")
        loader = SkillPackLoader(tmp_packs_dir)
        assert loader.load_pack(d) is None

    def test_load_all_skips_invalid_packs(self, tmp_packs_dir):
        create_valid_pack(tmp_packs_dir, "good-pack")
        d = tmp_packs_dir / "bad-pack"
        d.mkdir()
        (d / "skill.yaml").write_text("name: bad-pack")
        loader = SkillPackLoader(tmp_packs_dir)
        results = loader.load_all()
        names = [r["frontmatter"]["name"] for r in results]
        assert "good-pack" in names
        assert "bad-pack" not in names

    def test_load_all_from_nonexistent_dir(self):
        loader = SkillPackLoader("/nonexistent/path")
        assert loader.load_all() == []


class TestSkillPackMetadata:
    def test_pack_data_includes_knowledge(self, tmp_packs_dir):
        d = create_valid_pack(tmp_packs_dir, "knowledge-test")
        custom_knowledge = "## Coverage\n\nSpecific forensic knowledge.\n"
        write_knowledge(d, custom_knowledge)
        loader = SkillPackLoader(tmp_packs_dir)
        result = loader.load_pack(d)
        assert result is not None
        assert "pack_data" in result
        assert "forensic" in result["pack_data"]["knowledge"]

    def test_pack_data_includes_tools(self, tmp_packs_dir):
        d = tmp_packs_dir / "tooled-pack"
        d.mkdir()
        write_skill_yaml(d)
        write_readme(d)
        write_knowledge(d)
        (d / "tools.yaml").write_text(yaml.dump({
            "tools": [{"name": "tcpdump", "description": "Capture packets"}]
        }), encoding="utf-8")
        loader = SkillPackLoader(tmp_packs_dir)
        result = loader.load_pack(d)
        assert result is not None
        assert result["pack_data"]["tools"]["tools"][0]["name"] == "tcpdump"

    def test_pack_metadata_has_pack_format_flag(self, tmp_packs_dir):
        d = create_valid_pack(tmp_packs_dir, "format-check")
        loader = SkillPackLoader(tmp_packs_dir)
        result = loader.load_pack(d)
        assert result["metadata"]["pack_format"] is True

    def test_combined_text_includes_all_sections(self, tmp_packs_dir):
        d = create_valid_pack(tmp_packs_dir, "combined")
        loader = SkillPackLoader(tmp_packs_dir)
        result = loader.load_pack(d)
        raw = result["raw_text"]
        assert "combined" in raw
        assert "Overview" in raw
        assert "Knowledge" in raw


# ===================================================================
# Task 3 — SkillSelector Enhancement Tests
# ===================================================================

class TestEnhancedSkillSelector:
    @pytest.fixture
    def registry(self):
        r = SkillRegistry()
        r.register(make_registry_skill("web-xss", category="web", difficulty="beginner",
                                        tags=["web", "xss"]))
        r.register(make_registry_skill("malware-pe", category="malware", difficulty="advanced",
                                        tags=["malware", "pe"]))
        r.register(make_registry_skill("crypto-rsa", category="crypto", difficulty="intermediate",
                                        tags=["crypto", "rsa"]))
        r.register(make_registry_skill("forensics-memory", category="forensics", difficulty="intermediate",
                                        tags=["forensics", "memory"]))
        return r

    @pytest.mark.asyncio
    async def test_select_with_category_filter(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select(
            "analyze memory dump", category="forensics", limit=5,
        )
        assert len(results) >= 1
        for r in results:
            assert r["category"] == "forensics"

    @pytest.mark.asyncio
    async def test_select_with_category_no_match(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select(
            "analyze image", category="stego", limit=5,
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_select_with_difficulty_exact_match(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select(
            "web exploit", difficulty="beginner", limit=5,
        )
        assert len(results) >= 1
        # Beginner skills should rank higher
        assert results[0]["difficulty"] == "beginner"

    @pytest.mark.asyncio
    async def test_select_with_difficulty_and_category(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select(
            "rsa crypto", category="crypto", difficulty="intermediate", limit=5,
        )
        assert len(results) >= 1
        assert results[0]["category"] == "crypto"
        assert results[0]["difficulty"] == "intermediate"

    @pytest.mark.asyncio
    async def test_select_with_feedback_boost(self, registry):
        selector = SkillSelector(registry)
        feedback = [{"skill": "web-xss", "score": 0.8}]
        results = await selector.select(
            "web challenge", feedback=feedback, limit=5,
        )
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_select_with_feedback_penalize(self, registry):
        selector = SkillSelector(registry)
        feedback = [{"skill": "web-xss", "score": -0.5}]
        results = await selector.select(
            "web xss challenge", feedback=feedback, limit=5,
        )
        # web-xss may still appear but with lower score
        web_results = [r for r in results if r["name"] == "web-xss"]
        if web_results:
            assert web_results[0]["score"] < 5.0

    @pytest.mark.asyncio
    async def test_backward_compatible_no_filters(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select("web xss", limit=3)
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "web-xss" in names

    @pytest.mark.asyncio
    async def test_enhanced_output_includes_new_fields(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select("malware analysis", limit=3)
        if results:
            r = results[0]
            assert "difficulty" in r
            assert "supported_challenges" in r
            assert "verification_methods" in r


# ===================================================================
# Task 3 — Existing SkillSelector Backward Compatibility Tests
# ===================================================================

class TestSkillSelectorBackwardCompat:
    @pytest.mark.asyncio
    async def test_existing_select_signature_still_works(self):
        registry = SkillRegistry()
        registry.register(make_registry_skill("sql-injection", category="web"))
        selector = SkillSelector(registry)
        results = await selector.select("sql injection database", limit=3)
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "sql-injection" in names

    @pytest.mark.asyncio
    async def test_select_by_name_still_works(self):
        registry = SkillRegistry()
        registry.register(make_registry_skill("test-skill"))
        selector = SkillSelector(registry)
        result = await selector.select_by_name("test-skill")
        assert result is not None
        assert result["name"] == "test-skill"

    @pytest.mark.asyncio
    async def test_select_by_name_missing(self):
        selector = SkillSelector(SkillRegistry())
        result = await selector.select_by_name("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_select_returns_empty_for_nonsense(self):
        registry = SkillRegistry()
        registry.register(make_registry_skill("web-xss", category="web"))
        selector = SkillSelector(registry)
        results = await selector.select("zzzzzyyyyyyxxxxx", limit=3)
        assert len(results) == 0


# ===================================================================
# Task 4 — SkillContextBuilder Tests
# ===================================================================

class TestSkillContextBuilder:
    def make_skill(self, name: str, category: str = "test",
                   difficulty: str = "beginner",
                   tags: list[str] = None,
                   raw_text: str = None) -> dict:
        return {
            "name": name,
            "description": f"Skill for {name}",
            "category": category,
            "subdomain": category,
            "tags": tags or ["test"],
            "score": 0.95,
            "requires": [],
            "allowed_tools": ["tool1"],
            "token_estimate": 100,
            "raw_text": raw_text or f"# {name}\n\n## Coverage\n\nTechniques for {name}.\n\n## Steps\n1. Recon\n2. Exploit\n",
            "difficulty": difficulty,
            "supported_challenges": [f"challenge-{name}"],
            "verification_methods": [f"verify {name}"],
        }

    def test_builds_context_for_single_skill(self):
        builder = SkillContextBuilder()
        skills = [self.make_skill("sql-injection", category="web")]
        context = builder.build_context(skills)
        assert "<skill_context>" in context
        assert "</skill_context>" in context
        assert "sql-injection" in context
        assert "Skill:" in context
        assert "Knowledge:" in context

    def test_builds_context_for_multiple_skills(self):
        builder = SkillContextBuilder(budget=4096)
        skills = [
            self.make_skill("sql-injection", category="web"),
            self.make_skill("xss", category="web"),
        ]
        context = builder.build_context(skills)
        assert "sql-injection" in context
        assert "xss" in context

    def test_deduplicates_identical_content(self):
        builder = SkillContextBuilder(deduplicate=True, budget=4096)
        raw = "# same\n\n## Coverage\n\nIdentical content."
        skills = [
            self.make_skill("skill-a", raw_text=raw),
            self.make_skill("skill-b", raw_text=raw),
        ]
        context = builder.build_context(skills)
        # Only one should appear (content is identical after dedup)
        assert context.count("Skill:") == 1

    def test_empty_skill_list(self):
        builder = SkillContextBuilder()
        assert builder.build_context([]) == ""

    def test_respects_token_budget(self):
        builder = SkillContextBuilder(budget=30)
        skills = [self.make_skill("long-skill", raw_text="A" * 2000)]
        context = builder.build_context(skills)
        assert len(context) > 0
        assert "[...truncated]" in context or len(context) < 200

    def test_context_includes_verification_section(self):
        builder = SkillContextBuilder()
        skills = [self.make_skill("test-skill")]
        context = builder.build_context(skills)
        assert "Verification Methods" in context
        assert "verify test-skill" in context

    def test_context_includes_tools_section(self):
        builder = SkillContextBuilder()
        skills = [self.make_skill("tooled-skill")]
        context = builder.build_context(skills)
        assert "Required Tools" in context
        assert "tool1" in context

    def test_skill_without_knowledge_still_has_header(self):
        builder = SkillContextBuilder()
        skill = self.make_skill("minimal", raw_text="# minimal")
        context = builder.build_context([skill])
        assert "Skill: minimal" in context

    def test_context_includes_difficulty(self):
        builder = SkillContextBuilder()
        skills = [self.make_skill("advanced-skill", difficulty="advanced")]
        context = builder.build_context(skills)
        assert "advanced" in context

    def test_build_injectable_skills(self):
        builder = SkillContextBuilder()
        skills = [self.make_skill("injectable")]
        result = builder.build_injectable_skills(skills)
        assert len(result) == 1
        assert result[0]["name"] == "injectable"
        assert "raw_text" in result[0]
        assert "difficulty" in result[0]
        assert "verification_methods" in result[0]

    def test_build_injectable_empty(self):
        builder = SkillContextBuilder()
        assert builder.build_injectable_skills([]) == []

    def test_deduplication_across_injectable_skills(self):
        builder = SkillContextBuilder(deduplicate=True)
        raw = "Duplicate content"
        skills = [
            self.make_skill("a", raw_text=raw),
            self.make_skill("a", raw_text=raw),
        ]
        result = builder.build_injectable_skills(skills)
        assert len(result) == 1


# ===================================================================
# Integration: Pack Loading → Registry → Selector → Context
# ===================================================================

class TestSkillSystemIntegration:
    @pytest.mark.asyncio
    async def test_full_pack_lifecycle(self, tmp_packs_dir):
        d = create_valid_pack(tmp_packs_dir, "web-xss", overrides={
            "category": "web",
            "difficulty": "beginner",
            "tags": ["web", "xss"],
        })
        loader = SkillPackLoader(tmp_packs_dir)
        loaded = loader.load_pack(d)
        assert loaded is not None

        registry = SkillRegistry()
        registry.register(loaded)
        assert "web-xss" in registry

        selector = SkillSelector(registry)
        selected = await selector.select("xss attack", category="web", limit=3)
        assert len(selected) >= 1
        assert selected[0]["name"] == "web-xss"

        builder = SkillContextBuilder()
        context = builder.build_context(selected)
        assert "<skill_context>" in context
        assert "web-xss" in context

    @pytest.mark.asyncio
    async def test_integration_ranked_by_category_and_difficulty(self, tmp_packs_dir):
        for name, cat, diff in [
            ("web-easy", "web", "beginner"),
            ("web-hard", "web", "advanced"),
            ("crypto-mid", "crypto", "intermediate"),
        ]:
            d = tmp_packs_dir / name
            d.mkdir()
            write_skill_yaml(d, {"name": name, "description": f"skill {name}",
                                  "category": cat, "difficulty": diff,
                                  "tags": [cat, diff]})
            write_readme(d)
            write_knowledge(d)

        loader = SkillPackLoader(tmp_packs_dir)
        registry = SkillRegistry()
        for pack in loader.load_all():
            registry.register(pack)

        selector = SkillSelector(registry)
        results = await selector.select(
            "web application", category="web", difficulty="beginner", limit=5,
        )
        assert len(results) >= 1
        # web-easy should rank highest (matches both category and difficulty)
        assert results[0]["name"] == "web-easy"

    def test_packs_loaded_via_both_loaders(self, tmp_packs_dir):
        from skills_engine.loader import SkillLoader
        create_valid_pack(tmp_packs_dir, "pack-skill")
        pack_loader = SkillPackLoader(tmp_packs_dir)
        pack_results = pack_loader.load_all()
        assert len(pack_results) >= 1
        assert pack_results[0]["metadata"].get("pack_format") is True

    @pytest.mark.asyncio
    async def test_mixed_registry_selection_works(self, tmp_packs_dir):
        registry = SkillRegistry()
        registry.register(make_registry_skill("legacy-skill", category="legacy"))

        d = create_valid_pack(tmp_packs_dir, "pack-skill", overrides={"category": "pack"})
        loader = SkillPackLoader(tmp_packs_dir)
        registry.register(loader.load_pack(d))

        assert "legacy-skill" in registry
        assert "pack-skill" in registry

        selector = SkillSelector(registry)
        results = await selector.select("legacy", limit=5)
        names = [r["name"] for r in results]
        assert "legacy-skill" in names
