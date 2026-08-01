"""Tests for the Agent Skill Registry and registry-based routing.

Covers:
  - SkillDefinition fields (incl. version, enabled)
  - SkillRegistry registration and lookups
  - Keyword-based classification (routing)
  - Enabled/disabled routing control
  - register_agent adoption of live specialist instances
  - load_agent instantiation from import paths
  - YAML-backed registry loading and parity with CATEGORY_KEYWORDS
  - CoordinatorAgent routing through the registry (incl. DevOps)
  - Backward compatibility of the no-arg CoordinatorAgent
"""

import pytest

from agents.team.coordinator import CATEGORY_KEYWORDS, CoordinatorAgent
from agents.team.skill_registry import (
    SkillDefinition,
    SkillRegistry,
    load_skill_registry,
)
from agents.team.specialists.crypto_agent import CryptoAgent
from agents.team.specialists.devops_agent import DevOpsAgent
from agents.team.specialists.forensics_agent import ForensicsAgent
from agents.team.specialists.malware_agent import MalwareAnalysisAgent
from agents.team.specialists.web_agent import WebSecurityAgent

ALL_AGENTS = [
    MalwareAnalysisAgent(),
    WebSecurityAgent(),
    CryptoAgent(),
    ForensicsAgent(),
    DevOpsAgent(),
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
        assert {"malware", "web", "crypto", "forensics", "devops"} <= names

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
