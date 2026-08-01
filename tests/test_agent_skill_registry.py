"""Tests for the Agent Skill Registry and registry-based routing.

Covers:
  - SkillDefinition fields (incl. version, enabled)
  - SkillRegistry registration and lookups
  - Keyword-based classification (routing)
  - Enabled/disabled routing control
  - register_agent adoption of live specialist instances
  - load_agent instantiation from import paths
  - YAML-backed registry loading and parity with CATEGORY_KEYWORDS
  - CoordinatorAgent routing through the registry (incl. DevOps, Web Exploitation)
  - Web Exploitation Agent classification, findings, and dispatch
  - Binary Reverse Engineering Agent classification, findings, and dispatch
  - Pwn Agent classification, findings, and dispatch
  - Backward compatibility of the no-arg CoordinatorAgent
"""

import pytest

from agents.team.coordinator import CATEGORY_KEYWORDS, CoordinatorAgent
from agents.team.skill_registry import (
    SkillDefinition,
    SkillRegistry,
    load_skill_registry,
)
from agents.team.specialists.binary_reverse_agent import BinaryReverseAgent
from agents.team.specialists.crypto_agent import CryptoAgent
from agents.team.specialists.devops_agent import DevOpsAgent
from agents.team.specialists.forensics_agent import ForensicsAgent
from agents.team.specialists.malware_agent import MalwareAnalysisAgent
from agents.team.specialists.pwn_agent import PwnAgent
from agents.team.specialists.web_agent import WebSecurityAgent
from agents.team.specialists.web_exploit_agent import WebExploitAgent

ALL_AGENTS = [
    MalwareAnalysisAgent(),
    WebSecurityAgent(),
    CryptoAgent(),
    ForensicsAgent(),
    DevOpsAgent(),
    WebExploitAgent(),
    BinaryReverseAgent(),
    PwnAgent(),
]


def make_definition(**overrides) -> SkillDefinition:
    defaults = dict(
        name="devops",
        category="devops",
        agent="agents.team.specialists.devops_agent:DevOpsAgent",
        prompt="prompts/devops_expert.md",
        keywords=["docker", "kubernetes", "terraform", "pipeline"],
        capabilities=["docker_container_analysis", "kubernetes_analysis"],
    )
    defaults.update(overrides)
    return SkillDefinition(**defaults)


# ===================================================================
# SkillDefinition
# ===================================================================

class TestSkillDefinition:
    def test_all_fields_present(self):
        d = make_definition()
        assert d.name == "devops"
        assert d.category == "devops"
        assert d.agent == "agents.team.specialists.devops_agent:DevOpsAgent"
        assert d.prompt == "prompts/devops_expert.md"
        assert "docker" in d.keywords
        assert "kubernetes_analysis" in d.capabilities
        assert d.version == "1.0"
        assert d.enabled is True

    def test_defaults(self):
        d = SkillDefinition(name="x", category="x")
        assert d.agent == ""
        assert d.prompt == ""
        assert d.keywords == []
        assert d.capabilities == []
        assert d.version == "1.0"
        assert d.enabled is True

    def test_to_dict(self):
        d = make_definition()
        out = d.to_dict()
        assert out["name"] == "devops"
        assert out["category"] == "devops"
        assert out["enabled"] is True
        assert set(out.keys()) == {
            "name", "category", "agent", "prompt", "keywords",
            "capabilities", "version", "enabled",
        }


# ===================================================================
# SkillRegistry
# ===================================================================

class TestSkillRegistry:
    def test_register_and_get(self):
        r = SkillRegistry()
        r.register(make_definition())
        d = r.get("devops")
        assert d is not None
        assert d.name == "devops"

    def test_register_many(self):
        r = SkillRegistry()
        r.register_many([make_definition(name="devops", category="devops"),
                         make_definition(name="malware", category="malware")])
        assert len(r.list_skills()) == 2

    def test_get_by_name(self):
        r = SkillRegistry()
        r.register(make_definition())
        assert r.get_by_name("devops").category == "devops"

    def test_get_by_capability(self):
        r = SkillRegistry()
        r.register(make_definition())
        matches = r.get_by_capability("kubernetes_analysis")
        assert len(matches) == 1
        assert matches[0].category == "devops"

    def test_categories_include_fallback_keys(self):
        r = SkillRegistry(fallback_keywords={"malware": ["malware"]})
        assert "malware" in r.categories()

    def test_keywords_for_fallback_when_no_definition(self):
        r = SkillRegistry(fallback_keywords={"malware": ["virus", "trojan"]})
        assert r.keywords_for("malware") == ["virus", "trojan"]
        assert r.keywords_for("unknown") == []

    def test_registered_keywords_take_precedence(self):
        r = SkillRegistry(fallback_keywords={"devops": ["legacy"]})
        r.register(make_definition(keywords=["docker", "kubernetes"]))
        assert r.keywords_for("devops") == ["docker", "kubernetes"]

    def test_classify_matches_registered_keywords(self):
        r = SkillRegistry()
        r.register(make_definition(keywords=["kubernetes", "terraform"]))
        cats = r.classify("Set up a Kubernetes cluster with Terraform")
        assert "devops" in cats
        assert cats["devops"] == 1.0

    def test_classify_general_fallback(self):
        r = SkillRegistry()
        cats = r.classify("do something generic")
        assert cats == {"general": 1.0}

    def test_disabled_skill_excluded_from_routing(self):
        r = SkillRegistry()
        r.register(make_definition(keywords=["kubernetes"]))
        r.set_enabled("devops", False)
        cats = r.classify("Set up a Kubernetes cluster")
        assert "devops" not in cats
        assert "general" in cats

    def test_enabled_skill_reincluded(self):
        r = SkillRegistry()
        r.register(make_definition(keywords=["kubernetes"]))
        r.set_enabled("devops", False)
        r.set_enabled("devops", True)
        assert "devops" in r.classify("Set up a Kubernetes cluster")

    def test_register_agent_adopts_instance(self):
        r = SkillRegistry()
        d = r.register_agent(DevOpsAgent())
        assert d.category == "devops"
        assert d.name == "devops"
        assert "kubernetes_analysis" in d.capabilities
        assert d.agent == "agents.team.specialists.devops_agent:DevOpsAgent"
        assert d.prompt == "prompts/devops_expert.md"
        # No fallback keywords configured -> empty, but definition exists
        assert r.get("devops") is d

    def test_register_agent_preserves_existing_keywords(self):
        r = SkillRegistry()
        r.register(make_definition(keywords=["kubernetes", "docker"]))
        r.register_agent(DevOpsAgent())
        assert r.keywords_for("devops") == ["kubernetes", "docker"]

    def test_load_agent_instantiates(self):
        r = SkillRegistry()
        r.register(make_definition())
        agent = r.load_agent("devops")
        assert isinstance(agent, DevOpsAgent)
        assert agent.category == "devops"

    def test_load_agent_unknown_category(self):
        r = SkillRegistry()
        assert r.load_agent("nope") is None


# ===================================================================
# YAML-backed registry
# ===================================================================

class TestLoadSkillRegistry:
    def test_loads_all_definitions(self):
        r = load_skill_registry()
        names = {d.name for d in r.list_skills()}
        assert {"malware", "web", "crypto", "forensics", "devops", "web_exploitation", "binary_reverse", "pwn"} <= names

    def test_devops_entry_complete(self):
        r = load_skill_registry()
        d = r.get("devops")
        assert d is not None
        assert d.agent == "agents.team.specialists.devops_agent:DevOpsAgent"
        assert d.prompt == "prompts/devops_expert.md"
        assert "kubernetes" in d.keywords
        assert "ci_cd_pipeline_analysis" in d.capabilities
        assert d.version == "1.0"
        assert d.enabled is True

    def test_web_exploitation_entry_complete(self):
        r = load_skill_registry()
        d = r.get("web_exploitation")
        assert d is not None
        assert d.name == "web_exploitation"
        assert d.agent == "agents.team.specialists.web_exploit_agent:WebExploitAgent"
        assert d.prompt == "prompts/web_exploitation_expert.md"
        assert "sqli" in d.keywords
        assert "ssti" in d.keywords
        assert "sql_injection_analysis" in d.capabilities
        assert "exploit_verification" in d.capabilities
        assert d.version == "1.0"
        assert d.enabled is True

    def test_binary_reverse_entry_complete(self):
        r = load_skill_registry()
        d = r.get("binary_reverse")
        assert d is not None
        assert d.name == "binary_reverse"
        assert d.agent == "agents.team.specialists.binary_reverse_agent:BinaryReverseAgent"
        assert d.prompt == "prompts/binary_reverse_expert.md"
        assert "ghidra" in d.keywords
        assert "anti-debug" in d.keywords
        assert "elf_analysis" in d.capabilities
        assert "decompilation" in d.capabilities
        assert "anti_debugging_analysis" in d.capabilities
        assert d.version == "1.0"
        assert d.enabled is True

    def test_pwn_entry_complete(self):
        r = load_skill_registry()
        d = r.get("pwn")
        assert d is not None
        assert d.name == "pwn"
        assert d.agent == "agents.team.specialists.pwn_agent:PwnAgent"
        assert d.prompt == "prompts/pwn_expert.md"
        assert "pwntools" in d.keywords
        assert "ret2libc" in d.keywords
        assert "format string" in d.keywords
        assert "stack_overflow_analysis" in d.capabilities
        assert "rop_chain_development" in d.capabilities
        assert "remote_challenge_analysis" in d.capabilities
        assert d.version == "1.0"
        assert d.enabled is True

    def test_yaml_keywords_match_category_keywords(self):
        """The central YAML must stay in sync with CATEGORY_KEYWORDS."""
        r = load_skill_registry()
        for category, legacy_keywords in CATEGORY_KEYWORDS.items():
            assert set(r.keywords_for(category)) == set(legacy_keywords), category

    def test_yaml_classify_matches_legacy_classify(self):
        r = load_skill_registry()
        samples = [
            "Analyze this malware executable for viruses",
            "Check for SQL injection on the login endpoint",
            "Decrypt this base64 encoded RSA key",
            "Extract metadata and find hidden artifacts",
            "Set up a CI/CD pipeline with Docker and Kubernetes on AWS",
            "Do something generic",
        ]
        for sample in samples:
            from_yaml = r.classify(sample)
            from_legacy = SkillRegistry(fallback_keywords=CATEGORY_KEYWORDS).classify(sample)
            assert from_yaml == from_legacy, sample


# ===================================================================
# Word-boundary-aware classification (regression tests)
# ===================================================================

class TestWordBoundaryClassification:
    """Keywords must match as whole words, not as substrings of larger tokens."""

    # --- Positive: keywords embedded in text must still route ---

    @pytest.mark.parametrize("registry", [
        pytest.param(load_skill_registry(), id="yaml"),
        pytest.param(SkillRegistry(fallback_keywords=CATEGORY_KEYWORDS), id="legacy"),
    ])
    def test_elf_binary_routes_to_binary_reverse(self, registry):
        cats = registry.classify("Analyze this ELF binary using Ghidra")
        assert "binary_reverse" in cats
        assert cats["binary_reverse"] == max(cats.values())

    @pytest.mark.parametrize("registry", [
        pytest.param(load_skill_registry(), id="yaml"),
        pytest.param(SkillRegistry(fallback_keywords=CATEGORY_KEYWORDS), id="legacy"),
    ])
    def test_sql_injection_routes_to_web_exploitation(self, registry):
        cats = registry.classify("Exploit SQL injection vulnerability")
        assert "web_exploitation" in cats

    @pytest.mark.parametrize("registry", [
        pytest.param(load_skill_registry(), id="yaml"),
        pytest.param(SkillRegistry(fallback_keywords=CATEGORY_KEYWORDS), id="legacy"),
    ])
    def test_rop_chain_routes_to_pwn(self, registry):
        cats = registry.classify("Perform ROP chain exploitation")
        assert "pwn" in cats
        assert cats["pwn"] == max(cats.values())

    # --- Negative: keyword as a substring must NOT route ---

    @pytest.mark.parametrize("registry", [
        pytest.param(load_skill_registry(), id="yaml"),
        pytest.param(SkillRegistry(fallback_keywords=CATEGORY_KEYWORDS), id="legacy"),
    ])
    def test_login_is_not_forensics(self, registry):
        cats = registry.classify("Check the login page")
        assert "forensics" not in cats

    @pytest.mark.parametrize("registry", [
        pytest.param(load_skill_registry(), id="yaml"),
        pytest.param(SkillRegistry(fallback_keywords=CATEGORY_KEYWORDS), id="legacy"),
    ])
    def test_unix_is_not_pwn(self, registry):
        cats = registry.classify("Analyze the unix system")
        assert "pwn" not in cats

    @pytest.mark.parametrize("registry", [
        pytest.param(load_skill_registry(), id="yaml"),
        pytest.param(SkillRegistry(fallback_keywords=CATEGORY_KEYWORDS), id="legacy"),
    ])
    def test_myself_is_not_binary_reverse(self, registry):
        cats = registry.classify("Review myself application")
        assert "binary_reverse" not in cats


# ===================================================================
# Registry-based routing through the Coordinator
# ===================================================================

class TestWebExploitAgent:
    def test_identity(self):
        agent = WebExploitAgent()
        assert agent.name == "web_exploit_agent"
        assert agent.category == "web_exploitation"
        assert "sql_injection_analysis" in agent.capabilities
        assert "exploit_verification" in agent.capabilities

    @pytest.mark.asyncio
    async def test_analyze_sql_injection(self):
        agent = WebExploitAgent()
        result = await agent.analyze("Probe the login endpoint for SQL injection")
        assert result.agent_name == "web_exploit_agent"
        assert result.category == "web_exploitation"
        assert any("SQL injection" in f for f in result.findings)
        assert "sqlmap" in result.tools_used

    @pytest.mark.asyncio
    async def test_analyze_ssti(self):
        agent = WebExploitAgent()
        result = await agent.analyze("Template injection on the order page")
        assert any("SSTI" in f for f in result.findings)
        assert result.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_analyze_generic(self):
        agent = WebExploitAgent()
        result = await agent.analyze("Look at this application")
        assert result.findings
        assert "curl" in result.tools_used


class TestBinaryReverseAgent:
    def test_identity(self):
        agent = BinaryReverseAgent()
        assert agent.name == "binary_reverse_agent"
        assert agent.category == "binary_reverse"
        assert "elf_analysis" in agent.capabilities
        assert "pe_analysis" in agent.capabilities
        assert "decompilation" in agent.capabilities

    @pytest.mark.asyncio
    async def test_analyze_elf_binary(self):
        agent = BinaryReverseAgent()
        result = await agent.analyze("Reverse engineer this ELF binary to find the flag")
        assert result.agent_name == "binary_reverse_agent"
        assert result.category == "binary_reverse"
        assert any("ELF" in f for f in result.findings)
        assert "readelf" in result.tools_used

    @pytest.mark.asyncio
    async def test_analyze_obfuscated_binary(self):
        agent = BinaryReverseAgent()
        result = await agent.analyze("Deobfuscate the packed UPX binary with anti-debugging checks")
        assert any("Obfuscation" in f for f in result.findings)
        assert any("Packing" in f for f in result.findings)
        assert any("Anti-debugging" in f for f in result.findings)
        assert result.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_analyze_generic(self):
        agent = BinaryReverseAgent()
        result = await agent.analyze("Look at this file")
        assert result.findings
        assert "strings" in result.tools_used


class TestPwnAgent:
    def test_identity(self):
        agent = PwnAgent()
        assert agent.name == "pwn_agent"
        assert agent.category == "pwn"
        assert "stack_overflow_analysis" in agent.capabilities
        assert "rop_chain_development" in agent.capabilities
        assert "use_after_free_analysis" in agent.capabilities

    @pytest.mark.asyncio
    async def test_analyze_buffer_overflow(self):
        agent = PwnAgent()
        result = await agent.analyze("Find the offset and exploit the buffer overflow to call win")
        assert result.agent_name == "pwn_agent"
        assert result.category == "pwn"
        assert any("Stack/buffer overflow" in f for f in result.findings)
        assert "pwntools" in result.tools_used

    @pytest.mark.asyncio
    async def test_analyze_format_string(self):
        agent = PwnAgent()
        result = await agent.analyze("Leak the canary with a format string on the server")
        assert any("Format string" in f for f in result.findings)
        assert result.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_analyze_rop_ret2libc(self):
        agent = PwnAgent()
        result = await agent.analyze("Build a ROP chain to ret2libc and leak libc with pwntools")
        assert any("ROP" in f for f in result.findings)
        assert any("ret2libc" in f for f in result.findings)
        assert "ROPgadget" in result.tools_used

    @pytest.mark.asyncio
    async def test_analyze_generic(self):
        agent = PwnAgent()
        result = await agent.analyze("Look at this binary")
        assert result.findings
        assert "pwntools" in result.tools_used


# ===================================================================
# Registry-based routing through the Coordinator
# ===================================================================

class TestRegistryRouting:
    @pytest.mark.asyncio
    async def test_coordinator_routes_devops_via_registry(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate(
            "Design a GitHub Actions CI/CD pipeline, containerize with Docker, "
            "deploy to Kubernetes, and provision with Terraform and Prometheus monitoring"
        )
        assert "devops_agent" in result["agents_dispatched"]
        assert result["categories_identified"].get("devops", 0) > 0

    @pytest.mark.asyncio
    async def test_coordinator_registry_dispatches_only_devops(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate(
            "Set up Kubernetes deployment with Docker Compose"
        )
        assert result["agents_dispatched"] == ["devops_agent"]

    @pytest.mark.asyncio
    async def test_coordinator_registry_multi_category(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate("Analyze malware and web traffic")
        dispatched = set(result["agents_dispatched"])
        assert "malware_analysis_agent" in dispatched
        assert "web_security_agent" in dispatched

    @pytest.mark.asyncio
    async def test_coordinator_backward_compatible_no_registry(self):
        coordinator = CoordinatorAgent()
        cats = coordinator._classify("Analyze this malware executable for viruses")
        assert "malware" in cats

    @pytest.mark.asyncio
    async def test_coordinator_default_registry_is_fallback(self):
        coordinator = CoordinatorAgent()
        assert coordinator.skill_registry.keywords_for("devops") == CATEGORY_KEYWORDS["devops"]

    @pytest.mark.asyncio
    async def test_registry_agent_used_by_coordinator(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        agent = coordinator.skill_registry.load_agent("devops")
        assert isinstance(agent, DevOpsAgent)

    @pytest.mark.asyncio
    async def test_coordinator_routes_web_exploitation_via_registry(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate(
            "Find the SQL injection and perform SSTI template injection exploitation"
        )
        assert "web_exploit_agent" in result["agents_dispatched"]
        assert result["categories_identified"].get("web_exploitation", 0) > 0

    @pytest.mark.asyncio
    async def test_coordinator_registry_dispatches_only_web_exploitation(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate(
            "Perform SSRF exploitation against the internal service"
        )
        assert result["agents_dispatched"] == ["web_exploit_agent"]

    @pytest.mark.asyncio
    async def test_web_exploitation_does_not_break_existing_routing(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate("Decrypt this RSA key")
        assert result["agents_dispatched"] == ["crypto_agent"]

    @pytest.mark.asyncio
    async def test_web_exploitation_uses_yaml_keywords(self):
        registry = load_skill_registry()
        assert "web_exploitation" in CATEGORY_KEYWORDS
        assert set(registry.keywords_for("web_exploitation")) == set(CATEGORY_KEYWORDS["web_exploitation"])

    @pytest.mark.asyncio
    async def test_coordinator_routes_binary_reverse_via_registry(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate(
            "Reverse engineer this ELF binary with Ghidra and objdump"
        )
        assert "binary_reverse_agent" in result["agents_dispatched"]
        assert result["categories_identified"].get("binary_reverse", 0) > 0

    @pytest.mark.asyncio
    async def test_coordinator_registry_dispatches_only_binary_reverse(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate(
            "Deobfuscate the packed UPX binary with anti-debugging"
        )
        assert result["agents_dispatched"] == ["binary_reverse_agent"]

    @pytest.mark.asyncio
    async def test_binary_reverse_does_not_break_existing_routing(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate("Decrypt this AES key")
        assert result["agents_dispatched"] == ["crypto_agent"]

    @pytest.mark.asyncio
    async def test_binary_reverse_uses_yaml_keywords(self):
        registry = load_skill_registry()
        assert "binary_reverse" in CATEGORY_KEYWORDS
        assert set(registry.keywords_for("binary_reverse")) == set(CATEGORY_KEYWORDS["binary_reverse"])

    @pytest.mark.asyncio
    async def test_coordinator_routes_pwn_via_registry(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate(
            "Exploit the stack overflow on the pwn challenge with pwntools"
        )
        assert "pwn_agent" in result["agents_dispatched"]
        assert result["categories_identified"].get("pwn", 0) > 0

    @pytest.mark.asyncio
    async def test_coordinator_registry_dispatches_only_pwn(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate(
            "Leak the canary with a format string, then ret2libc with pwntools"
        )
        assert result["agents_dispatched"] == ["pwn_agent"]

    @pytest.mark.asyncio
    async def test_pwn_does_not_break_existing_routing(self):
        registry = load_skill_registry()
        coordinator = CoordinatorAgent(skill_registry=registry)
        coordinator.register_specialists(ALL_AGENTS)

        result = await coordinator.coordinate("Recover this steganography image")
        assert result["agents_dispatched"] == ["forensics_agent"]

    @pytest.mark.asyncio
    async def test_pwn_uses_yaml_keywords(self):
        registry = load_skill_registry()
        assert "pwn" in CATEGORY_KEYWORDS
        assert set(registry.keywords_for("pwn")) == set(CATEGORY_KEYWORDS["pwn"])
