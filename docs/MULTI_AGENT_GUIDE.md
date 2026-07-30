# Multi-Agent CTF Team Collaboration Framework

## Overview

The Multi-Agent Team Collaboration Framework enables multiple specialized cybersecurity agents to collaborate on a single CTF challenge. A `CoordinatorAgent` classifies the problem, delegates tasks to the appropriate `SpecialistAgent` instances, and aggregates their findings through an `EvidencePool`.

### Architecture

```
Challenge / User Request
    |
SupervisorAgent (optional: coordinator param)
    |
CoordinatorAgent
    |-- classifies problem domain(s)
    |-- selects relevant specialist agents
    |-- delegates tasks
    |-- collects findings
    |
Specialist Agents
    |-- MalwareAnalysisAgent (malware analysis)
    |-- WebSecurityAgent     (web security)
    |-- CryptoAgent          (cryptography)
    |-- ForensicsAgent       (forensics / stego)
    |
EvidencePool
    |-- deduplicates findings
    |-- ranks by confidence
    |-- provides consolidated report
    |
VerificationAgent (existing)
    |
LearningReportGenerator (existing)
```

## Components

### SpecialistAgent (Base Class)

All specialist agents inherit from `SpecialistAgent` in `agents/team/specialists/__init__.py`.

```python
class SpecialistAgent:
    name: str = ""
    capabilities: list[str] = []
    category: str = ""

    async def analyze(self, task: str, context: Optional[dict] = None) -> AgentFinding:
        raise NotImplementedError
```

#### Creating a New Specialist Agent

```python
from agents.team.specialists import SpecialistAgent
from agents.team.evidence import AgentFinding

class DNSSecurityAgent(SpecialistAgent):
    name = "dns_security_agent"
    category = "network"
    capabilities = ["dns_analysis", "zone_transfer_check", "dns_tunneling_detection"]

    async def analyze(self, task: str, context=None) -> AgentFinding:
        findings = []
        evidence = []
        if "dns" in task.lower():
            findings.append("DNS query analysis performed")
            evidence.append("DNS traffic pattern recorded")
        return AgentFinding(
            agent_name=self.name,
            findings=findings,
            evidence=evidence,
            confidence=0.8,
            tools_used=["dig", "nslookup"],
            category=self.category,
        )
```

### AgentFinding

The standard output from all specialist agents:

| Field | Type | Description |
|-------|------|-------------|
| `agent_name` | str | Name of the agent producing the finding |
| `findings` | list[str] | Key findings from the analysis |
| `evidence` | list[str] | Supporting evidence (file paths, data excerpts) |
| `confidence` | float | Confidence score (0.0 — 1.0) |
| `tools_used` | list[str] | Tools used during analysis |
| `category` | str | Domain category (malware, web, crypto, forensics) |

### TeamMessage

The communication protocol between Coordinator and Specialists:

| Field | Type | Description |
|-------|------|-------------|
| `type` | MessageType | TASK, FINDING, EVIDENCE, STATUS, CANCEL, ACK |
| `sender` | str | Sending agent name |
| `target` | str | Receiving agent name |
| `payload` | str | Message content |
| `evidence` | list[str] | Evidence items (for FINDING type) |
| `confidence` | float | Confidence score (for FINDING type) |
| `task_id` | str | Correlation ID linking task to response |
| `status` | str | pending / completed / failed |

### EvidencePool

Collects, deduplicates, and ranks findings:

```python
pool = EvidencePool()
pool.add_finding(finding)
pool.add_findings([f1, f2, f3])

all_findings = pool.get_all()
ranked = pool.get_ranked()                # sorted by confidence desc
high_conf = pool.get_high_confidence(0.7) # threshold filter
report = pool.get_consolidated_report()   # complete summary dict
```

### CoordinatorAgent

Orchestrates multi-agent analysis:

```python
coordinator = CoordinatorAgent()
coordinator.register_specialists([
    MalwareAnalysisAgent(),
    WebSecurityAgent(),
    CryptoAgent(),
    ForensicsAgent(),
])

result = await coordinator.coordinate("Analyze suspicious executable with hidden strings")
```

The `coordinate()` method returns:

| Key | Description |
|-----|-------------|
| `task` | Original task string |
| `categories_identified` | Dict of category → relevance score |
| `agents_dispatched` | List of agent names that were dispatched |
| `findings` | List of AgentFinding dicts from each agent |
| `consolidated` | Resolved findings (lead agent, summary, tools) |
| `evidence_pool` | EvidencePool consolidated report |
| `message_log` | Full message history for the session |

## Integration with SupervisorAgent

The `CoordinatorAgent` is integrated as an optional constructor parameter on `SupervisorAgent`:

```python
from agents.supervisor import SupervisorAgent
from agents.team import CoordinatorAgent
from agents.team.specialists.malware_agent import MalwareAnalysisAgent
from agents.team.specialists.web_agent import WebSecurityAgent

coordinator = CoordinatorAgent()
coordinator.register_specialists([MalwareAnalysisAgent(), WebSecurityAgent()])

supervisor = SupervisorAgent(
    llm=llm,
    registry=registry,
    coordinator=coordinator,  # optional — None disables team mode
    verifier=verifier,
    report_generator=report_generator,
)

result = await supervisor.run("Analyze suspicious PE file")
print(result["team_coordination"])  # coordinator result dict or None
```

When `coordinator` is `None` (default), the supervisor operates in its original single-agent dispatch mode for full backward compatibility.

### Backward Compatibility

- All existing `SupervisorAgent` constructors continue to work unchanged.
- The `coordinator` parameter defaults to `None`.
- The return dict gains a `team_coordination` key (`None` when unused).
- All existing agent contracts, skill injection, verification, and learning report generation remain unaffected.

## Specialist Agents

### MalwareAnalysisAgent
- **Category:** malware
- **Capabilities:** pe_analysis, ioc_extraction, malware_indicator_analysis, static_analysis, dynamic_analysis_guidance
- **Triggers:** PE files, executables, IOCs, packed/encrypted samples

### WebSecurityAgent
- **Category:** web
- **Capabilities:** http_analysis, vulnerability_pattern_analysis, request_analysis, owasp_top_ten_check, parameter_fuzzing_guidance
- **Triggers:** HTTP traffic, SQL injection, XSS, auth/session issues, API endpoints

### CryptoAgent
- **Category:** crypto
- **Capabilities:** encoding_analysis, hash_analysis, rsa_analysis, cipher_identification, key_analysis
- **Triggers:** Base64/hex encoding, hashes, RSA keys, XOR, encrypted data

### ForensicsAgent
- **Category:** forensics
- **Capabilities:** metadata_analysis, artifact_analysis, evidence_discovery, file_carving_guidance, timeline_analysis
- **Triggers:** EXIF/metadata, disk images, steganography, file timestamps, logs

## Testing

```bash
python -m pytest tests/test_multi_agent_system.py -v
```

The test suite covers:
- Specialist creation and analysis (26+ tests)
- AgentFinding and TeamMessage models
- EvidencePool deduplication, ranking, and consolidation
- CoordinatorAgent classification, selection, delegation, and resolution
- End-to-end multi-agent workflows
- SupervisorAgent backward compatibility
