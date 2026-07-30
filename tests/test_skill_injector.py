"""Tests for the SkillInjector."""

from skills_engine.injector import SkillInjector


SAMPLE_PROMPT = "You are a helpful assistant with cybersecurity expertise."


def make_skill(name: str, subdomain: str = "web", raw_text: str = None):
    return {
        "name": name,
        "subdomain": subdomain,
        "description": f"Skill for {name}",
        "tags": [subdomain],
        "category": subdomain,
        "score": 0.95,
        "requires": [],
        "allowed_tools": [],
        "token_estimate": 100,
        "raw_text": raw_text or f"# {name}\n\nDetailed technique for {name}.\n\n## Steps\n1. Recon\n2. Exploit\n3. Capture flag\n",
    }


class TestSkillInjector:
    def test_inject_adds_context_block(self):
        injector = SkillInjector(budget=2048)
        skills = [make_skill("sql-injection")]
        result = injector.inject(SAMPLE_PROMPT, skills)
        assert SAMPLE_PROMPT in result
        assert "<skill_context>" in result
        assert "sql-injection" in result
        assert "</skill_context>" in result

    def test_inject_empty_skills_returns_original(self):
        injector = SkillInjector()
        result = injector.inject(SAMPLE_PROMPT, [])
        assert result == SAMPLE_PROMPT

    def test_inject_multiple_skills(self):
        injector = SkillInjector(budget=4096)
        skills = [
            make_skill("sql-injection"),
            make_skill("xss"),
            make_skill("pcap-analysis", subdomain="forensics"),
        ]
        result = injector.inject(SAMPLE_PROMPT, skills)
        assert "sql-injection" in result
        assert "xss" in result
        assert "pcap-analysis" in result

    def test_inject_truncates_when_over_budget(self):
        injector = SkillInjector(budget=100)
        long_skill = make_skill("long-skill", raw_text="A" * 2000)
        result = injector.inject(SAMPLE_PROMPT, [long_skill])
        assert "[...truncated]" in result
        assert SAMPLE_PROMPT in result

    def test_inject_into_messages_inserts_after_system(self):
        injector = SkillInjector()
        messages = [
            {"role": "system", "content": "System prompt here"},
            {"role": "user", "content": "User query"},
        ]
        skills = [make_skill("xss")]
        result = injector.inject_into_messages(messages, skills)
        assert len(result) == 2
        assert "System prompt here" in result[0]["content"]
        assert "<skill_context>" in result[0]["content"]
        assert result[1]["role"] == "user"

    def test_inject_into_messages_no_skills(self):
        injector = SkillInjector()
        messages = [{"role": "system", "content": "Hi"}, {"role": "user", "content": "Test"}]
        result = injector.inject_into_messages(messages, [])
        assert result == messages

    def test_enrich_system_prompt(self):
        injector = SkillInjector()
        skills = [make_skill("forensics", subdomain="forensics")]
        result = injector.enrich_system_prompt("Base prompt", skills)
        assert "Base prompt" in result
        assert "forensics" in result
        assert "<skill_context>" in result

    def test_estimate_tokens(self):
        text = "Hello world, this is a test of the token estimator."
        estimated = SkillInjector._estimate_tokens(text)
        assert estimated > 0
        assert estimated <= len(text)

    def test_truncate(self):
        text = "A" * 1000
        result = SkillInjector._truncate(text, 50)
        assert len(result) < len(text)
        assert "[...truncated]" in result

    def test_truncate_short_text(self):
        text = "Short text"
        result = SkillInjector._truncate(text, 1000)
        assert result == text

    def test_injector_respects_budget_across_multiple_skills(self):
        injector = SkillInjector(budget=300)
        skills = [
            make_skill("s1", raw_text="X" * 800),
            make_skill("s2", raw_text="Y" * 800),
            make_skill("s3", raw_text="Z" * 800),
        ]
        result = injector.inject(SAMPLE_PROMPT, skills)
        # Not all skills should fit in 300 token budget
        total_skill_tokens = len(result) // 4 - len(SAMPLE_PROMPT) // 4
        assert total_skill_tokens <= 350  # allow some overhead for template
