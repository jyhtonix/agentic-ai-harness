"""Tests for the SkillSelector."""

import pytest
from skills_engine.registry import SkillRegistry
from skills_engine.selector import SkillSelector


def make_skill(name: str, subdomain: str = "web", tags: list[str] = None,
               category: str = "", requires: list[str] = None,
               token_budget: dict = None, raw_text: str = ""):
    return {
        "frontmatter": {
            "name": name,
            "description": f"A skill called {name} for testing.",
            "domain": "ctf",
            "subdomain": subdomain,
            "category": category or subdomain,
            "tags": tags or ["test"],
            "version": "1.0",
            "user_invocable": False,
            "requires": requires or [],
            "token_budget": token_budget or {"frontmatter": 10, "full_content": 50},
            "allowed_tools": [],
        },
        "metadata": {"path": f"skills/{name}"},
        "raw_text": raw_text or f"# {name}\n\nTest content here.\n",
    }


class TestSkillSelector:
    @pytest.fixture
    def registry(self):
        r = SkillRegistry()
        r.register(make_skill("sql-injection", subdomain="web", tags=["web", "sqli"]))
        r.register(make_skill("xss", subdomain="web", tags=["web", "xss"]))
        r.register(make_skill("pcap-analysis", subdomain="forensics", tags=["forensics", "pcap"]))
        r.register(make_skill("rsa-crypto", subdomain="crypto", tags=["crypto", "rsa"]))
        return r

    @pytest.mark.asyncio
    async def test_select_by_keyword(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select("sql injection database", limit=3)
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "sql-injection" in names

    @pytest.mark.asyncio
    async def test_select_finds_forensics(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select("pcap network capture analysis", limit=3)
        names = [r["name"] for r in results]
        assert "pcap-analysis" in names

    @pytest.mark.asyncio
    async def test_select_respects_budget(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select("web exploit", limit=5, budget=100)
        for r in results:
            assert r["token_estimate"] <= 100

    @pytest.mark.asyncio
    async def test_select_returns_empty_for_nonsense(self, registry):
        selector = SkillSelector(registry)
        results = await selector.select("zzzzzyyyyyxxxxx", limit=3)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_select_by_name(self, registry):
        selector = SkillSelector(registry)
        result = await selector.select_by_name("xss")
        assert result is not None
        assert result["name"] == "xss"
        assert result["subdomain"] == "web"

    @pytest.mark.asyncio
    async def test_select_by_name_missing(self, registry):
        selector = SkillSelector(registry)
        result = await selector.select_by_name("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_select_includes_requires(self, registry):
        r = SkillRegistry()
        r.register(make_skill("advanced-web", requires=["ctf-web"]))
        selector = SkillSelector(r)
        results = await selector.select("advanced web", limit=3)
        assert len(results) >= 1
        assert results[0]["requires"] == ["ctf-web"]

    @pytest.mark.asyncio
    async def test_select_includes_allowed_tools(self, registry):
        s = make_skill("tooled-skill", subdomain="web")
        s["frontmatter"]["allowed_tools"] = ["web_search", "code_runner"]
        r = SkillRegistry()
        r.register(s)
        selector = SkillSelector(r)
        results = await selector.select("tooled", limit=3)
        assert "web_search" in results[0]["allowed_tools"]
