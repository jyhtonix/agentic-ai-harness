# Agent Skill Registry — Architecture

This document describes the Agent Skill Registry, the central routing
system that decides which specialist agent handles a given user request.

---

## Overview

The Agent Skill Registry is a data-driven registry that maps **skills**
(expert domains) to **specialist agents**. It replaces the previously
hardcoded `CATEGORY_KEYWORDS` dictionary as the single source of truth
for routing, while remaining fully backward compatible.

```
User Request
    |
Coordinator
    |
Agent Skill Registry
    |
Specialist Agents
    |
Tools / LLM
```

### What problem it solves

Before the registry, routing was implemented as a Python dictionary
(`CATEGORY_KEYWORDS`) hardcoded inside `agents/team/coordinator.py`.
Adding a new expert required editing production source code, and the
metadata describing an expert was scattered across several places:

| Concern | Old location | New location |
|---------|--------------|--------------|
| Routing keywords | `coordinator.py` (hardcoded dict) | `skills/agent_skills.yaml` |
| Agent category / capabilities | agent class attributes | `skills/agent_skills.yaml` |
| Agent implementation | specialist agent class | specialist agent class (unchanged) |
| Expert prompt file | `prompts/*_expert.md` (unwired) | linked via `prompt` field |

The registry centralizes these into one editable definition file and a
small lookup/classification engine, so experts can be added or tuned
without changing source code.

---

## Components

### Files

| File | Purpose |
|------|---------|
| `agents/team/skill_registry.py` | `SkillDefinition`, `SkillRegistry`, `load_skill_registry()` |
| `skills/agent_skills.yaml` | Central definition file (single source of truth) |
| `agents/team/coordinator.py` | `CoordinatorAgent` uses the registry for classification |
| `tests/test_agent_skill_registry.py` | Registry + registry-based routing tests |

### SkillDefinition

Each skill is described by a `SkillDefinition` dataclass:

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Unique skill identifier (e.g. `devops`) |
| `category` | str | Routing category; must match the specialist's `category` |
| `agent` | str | Import path to the agent class: `"module:ClassName"` |
| `prompt` | str | Path to the expert prompt file (e.g. `prompts/devops_expert.md`) |
| `keywords` | list[str] | Trigger keywords used for task classification |
| `capabilities` | list[str] | Capabilities advertised by the specialist |
| `version` | str | Skill definition version |
| `enabled` | bool | `false` excludes the skill from routing |

### SkillRegistry

The registry is keyed by `category` and provides:

- **Registration** — `register()`, `register_many()`, and `register_agent(instance)`
  (the last adopts a live `SpecialistAgent`, refreshing its capabilities/agent
  path while preserving configured keywords).
- **Lookups** — `get()`, `get_by_name()`, `get_by_capability()`, `list_skills()`.
- **Classification** — `classify(text)` scores a task against keyword sets.
- **Instantiation** — `load_agent(category)` lazily builds an agent instance from
  its import path (no hard imports → no circular dependencies).
- **Runtime control** — `set_enabled(category, bool)` to toggle routing.

`load_skill_registry()` reads `skills/agent_skills.yaml` and returns a populated
registry, degrading gracefully (with a warning) if the file is missing.

---

## Agent Skill Registry vs. `skills_engine`

These are two distinct systems that should not be confused:

| | `skills_engine/` | Agent Skill Registry |
|---|---|---|
| **Concern** | Knowledge injection | Agent routing / dispatch |
| **Answer to** | "What domain knowledge should the agent see?" | "Which specialist should handle this request?" |
| **Source data** | `SKILL.md` files + YAML frontmatter (content packs) | `skills/agent_skills.yaml` definitions |
| **Key classes** | `SkillLoader`, `SkillRegistry`, `SkillSelector`, `SkillInjector` | `SkillDefinition`, `SkillRegistry`, `load_skill_registry()` |
| **Output** | Ranked knowledge packs injected into prompts | Category scores + selected specialist agents |
| **Directory** | `skills/ctf-*/`, `skills/solve-challenge/` | `skills/agent_skills.yaml` |
| **Registry module** | `skills_engine/registry.py` | `agents/team/skill_registry.py` |

In short: the `skills_engine` teaches an agent *how to think about a
domain*, while the Agent Skill Registry decides *which agent to send
the work to*. They are complementary and independent.

---

## How Routing Works

The routing pipeline lives in `CoordinatorAgent` (`agents/team/coordinator.py`):

```
User Request
    |
    v
CoordinatorAgent.coordinate(task)
    |
    v
_classify(task, context)  ──>  SkillRegistry.classify(text)
    |                            • tokenize / lowercase task text
    |                            • for each category: +2.0 per keyword hit
    |                            • normalize scores to weights (0–1)
    |                            • sorted descending; "general" fallback
    |
    v
_select_agents(categories)  ──>  match registered specialists by category
    |
    v
_delegate_and_collect(...)  ──>  each specialist returns an AgentFinding
    |
    v
EvidencePool  ──>  dedupe / rank / consolidated report
    |
    v
coordinated result  ──>  Supervisor synthesis
```

### Classification details

1. The task text (plus any context values) is lowercased.
2. For every known category, each registered keyword found in the text
   contributes `+2.0` to that category's raw score.
3. Raw scores are normalized into weights and sorted descending.
4. If no category scores, the result falls back to `{"general": 1.0}`.
5. Categories whose skill has `enabled: false` contribute no keywords and
   are therefore excluded from routing.

### Agent selection

`_select_agents()` iterates the coordinator's registered specialists and
selects any whose `category` appears in the classified scores. If no
specialist matches (e.g. only "general"), the coordinator falls back to
dispatching to **all** registered specialists.

### Backward compatibility

- `CoordinatorAgent()` with no arguments still works — it builds a registry
  seeded with `CATEGORY_KEYWORDS` as fallback keywords, preserving the legacy
  behavior exactly.
- Registered YAML keywords take precedence; `CATEGORY_KEYWORDS` remain as the
  fallback for any category without a definition.
- `_classify()`, `_select_agents()`, and `register_specialist()` retain their
  original signatures and semantics.

---

## Adding a New Agent

Adding a new expert requires **no source-code changes** beyond the agent
implementation itself. The steps:

### 1. Create the specialist agent class

`agents/team/specialists/<name>_agent.py`:

```python
from agents.team.specialists import SpecialistAgent
from agents.team.evidence import AgentFinding

class NetworkSecurityAgent(SpecialistAgent):
    name = "network_security_agent"
    category = "network"
    capabilities = ["dns_analysis", "tcp_analysis", "tunneling_detection"]

    async def analyze(self, task, context=None) -> AgentFinding:
        findings = []
        evidence = []
        # ... keyword-driven analysis ...
        return AgentFinding(
            agent_name=self.name,
            findings=findings,
            evidence=evidence,
            confidence=0.7,
            tools_used=["tcpdump"],
            category=self.category,
        )
```

### 2. Create the expert prompt

`prompts/network_expert.md` — follow the existing `*_expert.md` format.

### 3. Register the skill in `skills/agent_skills.yaml`

```yaml
- name: network
  category: network
  agent: "agents.team.specialists.network_agent:NetworkSecurityAgent"
  prompt: "prompts/network_expert.md"
  keywords: [network, dns, tcp, packet, pcap, tunnel]
  capabilities:
    - dns_analysis
    - tcp_analysis
    - tunneling_detection
  version: "1.0"
  enabled: true
```

> The keywords here are what make the new agent routable. Add it to
> `CATEGORY_KEYWORDS` as well only if you need the legacy fallback path
> to recognize the category too.

### 4. Register the agent at runtime

```python
from agents.team.coordinator import CoordinatorAgent
from agents.team.skill_registry import load_skill_registry
from agents.team.specialists.network_agent import NetworkSecurityAgent

coordinator = CoordinatorAgent(skill_registry=load_skill_registry())
coordinator.register_specialists([NetworkSecurityAgent(), ...])
```

### 5. Test

```bash
python -m pytest tests/test_agent_skill_registry.py -v
```

The registry tests verify YAML loading, classification, agent
instantiation, and coordinator routing — add a case for the new category.

---

## Example: DevOps Routing

The `devops` skill routes infrastructure/CI-CD requests to `DevOpsAgent`:

```
"Set up a GitHub Actions pipeline, containerize with Docker,
 deploy to Kubernetes, provision AWS with Terraform, add Prometheus"
                    |
                    v
classify -> {'devops': 1.0}
                    |
                    v
agents_dispatched -> ['devops_agent']
```

---

## Example: Web Exploitation Routing

The `web_exploitation` skill routes web-CTF/offensive web requests to
`WebExploitAgent` (`agents/team/specialists/web_exploit_agent.py`):

```
"Probe the login endpoint for SQL injection, then exploit the SSTI"
                    |
                    v
classify -> {'web_exploitation': 1.0}
                    |
                    v
agents_dispatched -> ['web_exploit_agent']
```

The agent covers a recon→hypothesis→verify workflow across injection,
access-control, client-side, and application-level vulnerability classes,
and advertises tooling such as `sqlmap`, `ffuf`, `gobuster`, `nuclei`,
and `burp` for each analyzed surface.

### How Web Exploitation was added

The agent follows the standard "Adding a New Agent" steps above:

| Step | Artifact |
|------|----------|
| Specialist class | `agents/team/specialists/web_exploit_agent.py` — `WebExploitAgent` (category `web_exploitation`) |
| Expert prompt | `prompts/web_exploitation_expert.md` — workflow + vulnerability + tooling guidance |
| YAML registration | `skills/agent_skills.yaml` — `web_exploitation` entry with keywords/capabilities |
| Legacy fallback | `CATEGORY_KEYWORDS["web_exploitation"]` in `coordinator.py` kept in sync with the YAML keywords |
| Tests | `test_agent_skill_registry.py::TestWebExploitAgent` + routing cases in `TestRegistryRouting` |

The parity test `test_yaml_keywords_match_category_keywords` enforces that
the YAML keywords and the `CATEGORY_KEYWORDS` fallback stay identical, so
both routing paths classify identically.

See `tests/test_agent_skill_registry.py::TestRegistryRouting` for the
full registry-based routing tests.

---

## Example: Binary Reverse Engineering Routing

The `binary_reverse` skill routes binary-reverse-engineering / CTF binary
challenges to `BinaryReverseAgent`
(`agents/team/specialists/binary_reverse_agent.py`):

```
"Reverse engineer this ELF binary with Ghidra and objdump"
                    |
                    v
classify -> {'binary_reverse': 1.0}
                    |
                    v
agents_dispatched -> ['binary_reverse_agent']
```

The agent drives an identify→static→dynamic→decompile workflow across ELF
and PE targets, covering assembly basics, calling conventions, symbols,
obfuscation, packing, anti-debugging, and malware-style analysis. It
advertises tooling such as `ghidra`, `ida`, `x64dbg`, `objdump`, `strings`,
`readelf`, `radare2`, and `angr`.

### How Binary Reverse Engineering was added

The agent follows the standard "Adding a New Agent" steps above:

| Step | Artifact |
|------|----------|
| Specialist class | `agents/team/specialists/binary_reverse_agent.py` — `BinaryReverseAgent` (category `binary_reverse`) |
| Expert prompt | `prompts/binary_reverse_expert.md` — workflow + topics + tooling guidance |
| YAML registration | `skills/agent_skills.yaml` — `binary_reverse` entry with keywords/capabilities |
| Legacy fallback | `CATEGORY_KEYWORDS["binary_reverse"]` in `coordinator.py` kept in sync with the YAML keywords |
| Tests | `test_agent_skill_registry.py::TestBinaryReverseAgent` + routing cases in `TestRegistryRouting` |

Keywords were chosen to avoid substring collisions with existing categories
(e.g. no bare `pe`, `arm`, or `vm` tokens), and the parity test
`test_yaml_keywords_match_category_keywords` keeps the YAML keywords and
the `CATEGORY_KEYWORDS` fallback identical.

See `tests/test_agent_skill_registry.py::TestRegistryRouting` for the
full registry-based routing tests.

---

## Example: Binary Exploitation (Pwn) Routing

The `pwn` skill routes binary-exploitation / pwn CTF challenges to
`PwnAgent` (`agents/team/specialists/pwn_agent.py`):

```
"Leak the canary with a format string, then ret2libc with pwntools"
                    |
                    v
classify -> {'pwn': 1.0}
                    |
                    v
agents_dispatched -> ['pwn_agent']
```

The agent runs a protections→vulnerability→strategy→local→remote workflow
across stack/heap corruption, format strings, and use-after-free classes,
and plans mitigation bypasses for ASLR, NX, PIE, and canaries. It
advertises exploit-development tooling such as `pwntools`, `ROPgadget`,
`ropper`, `libc-database`, and `gdb`.

### How Pwn was added

The agent follows the standard "Adding a New Agent" steps above:

| Step | Artifact |
|------|----------|
| Specialist class | `agents/team/specialists/pwn_agent.py` — `PwnAgent` (category `pwn`) |
| Expert prompt | `prompts/pwn_expert.md` — workflow + mitigations + tooling guidance |
| YAML registration | `skills/agent_skills.yaml` — `pwn` entry with keywords/capabilities |
| Legacy fallback | `CATEGORY_KEYWORDS["pwn"]` in `coordinator.py` kept in sync with the YAML keywords |
| Tests | `test_agent_skill_registry.py::TestPwnAgent` + routing cases in `TestRegistryRouting` |

Keywords were chosen to avoid substring collisions with existing categories
(e.g. no bare `exploit` or `shell` tokens that would collide with
`web_exploitation`/`malware`), and the parity test
`test_yaml_keywords_match_category_keywords` keeps the YAML keywords and
the `CATEGORY_KEYWORDS` fallback identical.

See `tests/test_agent_skill_registry.py::TestRegistryRouting` for the
full registry-based routing tests.
