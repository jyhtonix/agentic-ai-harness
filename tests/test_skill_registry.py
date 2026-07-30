"""Tests for the SkillRegistry."""

import pytest
from skills_engine.registry import SkillRegistry


def make_skill(name: str, subdomain: str = "web", tags: list[str] = None, category: str = "", user_invocable: bool = False):
    return {
        "frontmatter": {
            "name": name,
            "description": f"A test skill called {name}.",
            "domain": "ctf",
            "subdomain": subdomain,
            "category": category or subdomain,
            "tags": tags or ["test"],
            "version": "1.0",
            "user_invocable": user_invocable,
            "requires": [],
        },
        "metadata": {"path": f"skills/{name}"},
    }


class TestSkillRegistry:
    def test_register_and_get(self):
        r = SkillRegistry()
        skill = make_skill("test-skill")
        r.register(skill)
        assert r.get("test-skill") is skill
        assert "test-skill" in r

    def test_get_missing(self):
        r = SkillRegistry()
        assert r.get("nonexistent") is None

    def test_get_frontmatter(self):
        r = SkillRegistry()
        r.register(make_skill("fm-skill"))
        fm = r.get_frontmatter("fm-skill")
        assert fm is not None
        assert fm["name"] == "fm-skill"

    def test_get_frontmatter_missing(self):
        r = SkillRegistry()
        assert r.get_frontmatter("ghost") is None

    def test_list(self):
        r = SkillRegistry()
        r.register(make_skill("alpha"))
        r.register(make_skill("beta"))
        listing = r.list()
        assert "alpha" in listing
        assert "beta" in listing
        assert len(listing) == 2

    def test_list_names(self):
        r = SkillRegistry()
        r.register(make_skill("a"))
        r.register(make_skill("b"))
        names = r.list_names()
        assert "a" in names
        assert "b" in names

    def test_search_by_name(self):
        r = SkillRegistry()
        r.register(make_skill("sql-injection"))
        r.register(make_skill("xss-attack"))
        results = r.search("sql")
        assert len(results) >= 1
        assert results[0]["name"] == "sql-injection"

    def test_search_by_tag(self):
        r = SkillRegistry()
        r.register(make_skill("crypto-rsa", tags=["crypto", "rsa"]))
        r.register(make_skill("crypto-aes", tags=["crypto", "aes"]))
        results = r.search("rsa")
        assert len(results) >= 1

    def test_search_by_subdomain(self):
        r = SkillRegistry()
        r.register(make_skill("web-1", subdomain="web"))
        r.register(make_skill("pwn-1", subdomain="pwn"))
        results = r.search("pwn")
        assert results[0]["name"] == "pwn-1"

    def test_get_by_subdomain(self):
        r = SkillRegistry()
        r.register(make_skill("w1", subdomain="web"))
        r.register(make_skill("w2", subdomain="web"))
        r.register(make_skill("p1", subdomain="pwn"))
        web_skills = r.get_by_subdomain("web")
        assert len(web_skills) == 2

    def test_get_by_category(self):
        r = SkillRegistry()
        r.register(make_skill("a", category="web"))
        r.register(make_skill("b", category="crypto"))
        crypto_skills = r.get_by_category("crypto")
        assert len(crypto_skills) == 1

    def test_get_by_tag(self):
        r = SkillRegistry()
        r.register(make_skill("xss", tags=["web", "xss"]))
        r.register(make_skill("sqli", tags=["web", "sqli"]))
        web_skills = r.get_by_tag("web")
        assert len(web_skills) == 2

    def test_get_categories(self):
        r = SkillRegistry()
        r.register(make_skill("a", category="web"))
        r.register(make_skill("b", category="web"))
        r.register(make_skill("c", category="crypto"))
        cats = r.get_categories()
        assert cats["web"] == 2
        assert cats["crypto"] == 1

    def test_get_user_invocable(self):
        r = SkillRegistry()
        r.register(make_skill("hidden", user_invocable=False))
        r.register(make_skill("runner", user_invocable=True))
        invocable = r.get_user_invocable()
        assert len(invocable) == 1
        assert invocable[0]["name"] == "runner"

    def test_remove(self):
        r = SkillRegistry()
        r.register(make_skill("temp"))
        assert "temp" in r
        r.remove("temp")
        assert "temp" not in r

    def test_register_many(self):
        r = SkillRegistry()
        skills = [make_skill("a"), make_skill("b"), make_skill("c")]
        r.register_many(skills)
        assert len(r) == 3

    def test_len(self):
        r = SkillRegistry()
        assert len(r) == 0
        r.register(make_skill("x"))
        assert len(r) == 1

    def test_iteration(self):
        r = SkillRegistry()
        r.register(make_skill("i1"))
        r.register(make_skill("i2"))
        names = {s["frontmatter"]["name"] for s in r}
        assert names == {"i1", "i2"}

    def test_set_index(self):
        r = SkillRegistry()
        r.set_index({"version": "1.0", "total_skills": 0, "skills": []})
        # no crash
