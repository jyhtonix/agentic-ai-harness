"""
Tests for SOC agents, frameworks, tools, and workflow.

Test coverage:
  - Framework reference data (MITRE ATT&CK, kill chain, NIST CSF)
  - SOC domain models (Alert, IOC, Finding, Incident)
  - IOC Check Tool (parsing, validation, edge cases)
  - Log Parser Tool (syslog, apache, JSON, auto-detect)
  - Alert Analyst Agent (message protocol, task processing)
  - Threat Hunter Agent (message protocol, task processing)
  - Malware Analyst Agent (message protocol, task processing)
  - Incident Responder Agent (message protocol, task processing)
  - SOC workflow integration
  - API registration
"""

import pytest
from models.llm import LLM, LLMResponse, LLMUsage
from core.protocol import AgentMessage

# ---------------------------------------------------------------------------
# Framework tests
# ---------------------------------------------------------------------------

from soc.frameworks import (
    lookup_technique,
    search_techniques,
    ENTERPRISE_TECHNIQUES,
    KILL_CHAIN_STAGES,
    NIST_CSF_FUNCTIONS,
    severity_score,
    service_for_port,
)


class TestFrameworks:
    def test_lookup_technique_by_id(self):
        t = lookup_technique("T1078")
        assert t is not None
        assert t.name == "Valid Accounts"
        assert t.tactic.startswith("TA0001")

    def test_lookup_technique_case_insensitive(self):
        t = lookup_technique("t1566")
        assert t is not None
        assert t.name == "Phishing"

    def test_lookup_technique_missing(self):
        assert lookup_technique("T9999") is None

    def test_search_techniques_by_name(self):
        results = search_techniques("phishing")
        assert len(results) >= 1
        assert any("Phishing" in r.name for r in results)

    def test_search_techniques_by_tactic(self):
        results = search_techniques("credential access")
        assert len(results) >= 1

    def test_search_techniques_no_match(self):
        results = search_techniques("nonexistent_technique_xyz")
        assert results == []

    def test_enterprise_techniques_populated(self):
        assert len(ENTERPRISE_TECHNIQUES) >= 20

    def test_kill_chain_stages(self):
        assert len(KILL_CHAIN_STAGES) == 7
        assert "Reconnaissance" in KILL_CHAIN_STAGES
        assert "Actions on Objectives" in KILL_CHAIN_STAGES

    def test_nist_csf_functions(self):
        assert "Identify" in NIST_CSF_FUNCTIONS
        assert "Respond" in NIST_CSF_FUNCTIONS
        assert "Recover" in NIST_CSF_FUNCTIONS
        assert len(NIST_CSF_FUNCTIONS["Protect"]) >= 3

    def test_severity_score(self):
        assert severity_score("Critical") == 5
        assert severity_score("Informational") == 1
        assert severity_score("Unknown") == 0

    def test_service_for_port(self):
        assert service_for_port(22) == "SSH"
        assert service_for_port(443) == "HTTPS"
        assert service_for_port(9999) == "Unknown"


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

from soc.models import Alert, IOC, LogEntry, Finding, Incident


class TestModels:
    def test_alert_creation(self):
        alert = Alert(
            id="ALERT-001",
            title="Suspicious PowerShell",
            description="PowerShell executed with encoded command",
            source="EDR",
            severity="High",
            mitre_techniques=["T1059"],
            kill_chain_stage="Execution",
            indicators=["powershell.exe -enc"],
            affected_hosts=["SRV-DC01"],
        )
        assert alert.id == "ALERT-001"
        assert alert.to_dict()["mitre_techniques"] == ["T1059"]

    def test_ioc_creation(self):
        ioc = IOC(value="192.168.1.100", ioc_type="ip", confidence=0.8)
        assert ioc.to_dict()["type"] == "ip"
        assert ioc.to_dict()["confidence"] == 0.8

    def test_finding_creation(self):
        f = Finding(
            title="RDP Brute Force",
            description="Multiple RDP failures from 10.0.0.50",
            severity="High",
            mitre_technique="T1110",
            recommendation="Enable account lockout policies",
        )
        d = f.to_dict()
        assert d["severity"] == "High"
        assert d["mitre_technique"] == "T1110"

    def test_incident_creation(self):
        inc = Incident(
            id="INC-001",
            title="Ransomware Outbreak",
            description="File encryption detected on 5 workstations",
            severity="Critical",
            findings=[Finding(title="Encryption detected", description="Files being renamed")],
            timeline=["08:00 - Alert fired", "08:05 - Analyst assigned"],
            containment_actions=["Isolate workstations"],
        )
        d = inc.to_dict()
        assert d["severity"] == "Critical"
        assert len(d["timeline"]) == 2
        assert len(d["findings"]) == 1


# ---------------------------------------------------------------------------
# Tool tests
# ---------------------------------------------------------------------------

from tools.ioc_check import IOCCheckTool
from tools.log_parser import LogParserTool


class TestIOCCheckTool:
    @pytest.mark.asyncio
    async def test_extract_ip(self):
        tool = IOCCheckTool()
        result = await tool.execute(text="Connection from 10.0.0.5")
        assert "10.0.0.5" in result
        assert "ip" in result

    @pytest.mark.asyncio
    async def test_extract_md5(self):
        tool = IOCCheckTool()
        result = await tool.execute(text="Hash: d41d8cd98f00b204e9800998ecf8427e")
        assert "d41d8cd98f00b204e9800998ecf8427e" in result
        assert "md5" in result

    @pytest.mark.asyncio
    async def test_extract_sha256(self):
        h = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        tool = IOCCheckTool()
        result = await tool.execute(text=f"Hash: {h}")
        assert h in result
        assert "sha256" in result

    @pytest.mark.asyncio
    async def test_extract_domain(self):
        tool = IOCCheckTool()
        result = await tool.execute(text="C2 at malicious.example.com")
        assert "malicious.example.com" in result

    @pytest.mark.asyncio
    async def test_extract_url(self):
        tool = IOCCheckTool()
        result = await tool.execute(text="Download from https://evil.com/payload.exe")
        assert "https://evil.com/payload.exe" in result

    @pytest.mark.asyncio
    async def test_no_text_returns_message(self):
        tool = IOCCheckTool()
        result = await tool.execute(text="")
        assert "No text provided" in result

    @pytest.mark.asyncio
    async def test_no_iocs_found(self):
        tool = IOCCheckTool()
        result = await tool.execute(text="This text has no indicators whatsoever.")
        assert "No IOCs found" in result

    @pytest.mark.asyncio
    async def test_multiple_ioc_types(self):
        tool = IOCCheckTool()
        text = "IP 10.0.0.1 connected to evil.com with hash a" + "b" * 31
        result = await tool.execute(text=text)
        assert "10.0.0.1" in result

    @pytest.mark.asyncio
    async def test_private_ip_marked(self):
        tool = IOCCheckTool()
        result = await tool.execute(text="Internal: 192.168.1.1")
        assert "192.168.1.1" in result

    @pytest.mark.asyncio
    async def test_execute_with_kwargs(self):
        tool = IOCCheckTool()
        result = await tool.execute(text="IP 1.2.3.4")
        assert "1.2.3.4" in result

    @pytest.mark.asyncio
    async def test_tool_metadata(self):
        tool = IOCCheckTool()
        assert tool.name == "ioc_check"
        assert "indicators of compromise" in tool.description.lower()


class TestLogParserTool:
    @pytest.mark.asyncio
    async def test_parse_syslog(self):
        tool = LogParserTool()
        log = "Mar 15 10:30:45 server01 sshd[1234]: Failed password for root from 10.0.0.5 port 22"
        result = await tool.execute(log_text=log)
        assert "sshd" in result or "Failed" in result
        assert "1 log" in result

    @pytest.mark.asyncio
    async def test_parse_apache_combined(self):
        tool = LogParserTool()
        log = '192.168.1.1 - - [10/Mar/2025:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 2326 "https://google.com" "Mozilla/5.0"'
        result = await tool.execute(log_text=log, format="apache")
        assert "192.168.1.1" in result
        assert "GET" in result

    @pytest.mark.asyncio
    async def test_parse_json_log(self):
        tool = LogParserTool()
        log = '{"timestamp": "2025-03-15T10:30:00", "event_type": "login", "src_ip": "10.0.0.5", "message": "Failed login attempt"}'
        result = await tool.execute(log_text=log, format="json")
        assert "10.0.0.5" in result
        assert "login" in result

    @pytest.mark.asyncio
    async def test_auto_detect_json(self):
        tool = LogParserTool()
        log = '{"message": "test", "src_ip": "10.0.0.1"}'
        result = await tool.execute(log_text=log)
        assert "1 log" in result

    @pytest.mark.asyncio
    async def test_auto_detect_apache(self):
        tool = LogParserTool()
        log = '1.2.3.4 - - [01/Jan/2025:00:00:00 +0000] "GET / HTTP/1.1" 200 1234 "-" "curl/7.0"'
        result = await tool.execute(log_text=log)
        assert "1.2.3.4" in result

    @pytest.mark.asyncio
    async def test_empty_log(self):
        tool = LogParserTool()
        result = await tool.execute(log_text="")
        assert "No log text" in result

    @pytest.mark.asyncio
    async def test_tool_metadata(self):
        tool = LogParserTool()
        assert tool.name == "log_parser"
        assert "firewall" in tool.description.lower()


# ---------------------------------------------------------------------------
# Agent tests
# ---------------------------------------------------------------------------


class FakeLLM(LLM):
    """Deterministic LLM stub with configurable responses."""

    def __init__(self):
        self.calls = []
        self.default_response = "Analysis complete.\n**Severity:** High\n**MITRE ATT&CK:** T1059 - Command and Scripting Interpreter\n**Investigation Steps:**\n1. Check process tree\n2. Review network connections"

    def set_response(self, response: str):
        self.default_response = response

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return LLMResponse(content=self.default_response, usage=LLMUsage(
            prompt_tokens=50, completion_tokens=30, total_tokens=80,
        ))


from agents.alert_analyst import AlertAnalystAgent
from agents.threat_hunter import ThreatHunterAgent
from agents.malware_analyst import MalwareAnalystAgent
from agents.incident_responder import IncidentResponderAgent


class TestAlertAnalystAgent:
    @pytest.mark.asyncio
    async def test_agent_name(self):
        agent = AlertAnalystAgent(FakeLLM())
        assert agent.name == "alert_analyst"

    @pytest.mark.asyncio
    async def test_process_task_returns_analysis(self):
        llm = FakeLLM()
        agent = AlertAnalystAgent(llm)
        result = await agent.process_task(
            "Alert: Suspicious PowerShell from workstation-05"
        )
        assert len(result) > 0
        assert len(llm.calls) == 1

    @pytest.mark.asyncio
    async def test_receive_message(self):
        agent = AlertAnalystAgent(FakeLLM())
        msg = AgentMessage(
            sender="supervisor",
            receiver="alert_analyst",
            task="Analyse EDR alert on SRV-001",
            conversation_id="conv-1",
        )
        reply = await agent.receive(msg)
        assert reply.status == "completed"
        assert reply.receiver == "supervisor"
        assert reply.sender == "alert_analyst"
        assert len(reply.response) > 0

    @pytest.mark.asyncio
    async def test_receive_failure_returns_failed_status(self):
        class BrokenLLM(FakeLLM):
            async def chat(self, messages, **kwargs):
                raise RuntimeError("LLM unavailable")

        agent = AlertAnalystAgent(BrokenLLM())
        msg = AgentMessage(sender="supervisor", receiver="alert_analyst", task="Analyse")
        reply = await agent.receive(msg)
        assert reply.status == "failed"

    @pytest.mark.asyncio
    async def test_conversation_history(self):
        agent = AlertAnalystAgent(FakeLLM())
        msg = AgentMessage(sender="supervisor", receiver="alert_analyst", task="Analyse")
        await agent.receive(msg)
        assert len(agent.conversation_history) >= 2

    @pytest.mark.asyncio
    async def test_legacy_execute_compatibility(self):
        agent = AlertAnalystAgent(FakeLLM())
        from core.agent import AgentContext
        ctx = AgentContext(task_id="1", objective="Analyse alert", plan={"step": "Triage SIEM alert"})
        result = await agent.execute(ctx)
        assert result.success is True
        assert len(result.output) > 0

    @pytest.mark.asyncio
    async def test_system_prompt_includes_mitre(self):
        agent = AlertAnalystAgent(FakeLLM())
        assert "MITRE" in agent.system_prompt


class TestThreatHunterAgent:
    @pytest.mark.asyncio
    async def test_agent_name(self):
        agent = ThreatHunterAgent(FakeLLM())
        assert agent.name == "threat_hunter"

    @pytest.mark.asyncio
    async def test_process_task_returns_report(self):
        llm = FakeLLM()
        agent = ThreatHunterAgent(llm)
        result = await agent.process_task("Hunt for IOCs related to APT-29 campaigns")
        assert len(result) > 0
        assert len(llm.calls) == 1

    @pytest.mark.asyncio
    async def test_receive_message(self):
        agent = ThreatHunterAgent(FakeLLM())
        msg = AgentMessage(sender="supervisor", receiver="threat_hunter", task="Hunt for anomalies in auth logs")
        reply = await agent.receive(msg)
        assert reply.status == "completed"
        assert reply.receiver == "supervisor"

    @pytest.mark.asyncio
    async def test_system_prompt_includes_ioc(self):
        agent = ThreatHunterAgent(FakeLLM())
        assert "IOC" in agent.system_prompt or "hypothesis" in agent.system_prompt


class TestMalwareAnalystAgent:
    @pytest.mark.asyncio
    async def test_agent_name(self):
        agent = MalwareAnalystAgent(FakeLLM())
        assert agent.name == "malware_analyst"

    @pytest.mark.asyncio
    async def test_process_task_with_hash(self):
        llm = FakeLLM()
        agent = MalwareAnalystAgent(llm)
        result = await agent.process_task(
            "Analyse sample: SHA256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_receive_sandbox_report(self):
        agent = MalwareAnalystAgent(FakeLLM())
        msg = AgentMessage(
            sender="threat_hunter",
            receiver="malware_analyst",
            task="Interpret sandbox report for ransomware sample",
        )
        reply = await agent.receive(msg)
        assert reply.status == "completed"

    @pytest.mark.asyncio
    async def test_system_prompt_includes_static_dynamic(self):
        agent = MalwareAnalystAgent(FakeLLM())
        assert "static" in agent.system_prompt.lower()
        assert "dynamic" in agent.system_prompt.lower()


class TestIncidentResponderAgent:
    @pytest.mark.asyncio
    async def test_agent_name(self):
        agent = IncidentResponderAgent(FakeLLM())
        assert agent.name == "incident_responder"

    @pytest.mark.asyncio
    async def test_process_task_returns_plan(self):
        llm = FakeLLM()
        agent = IncidentResponderAgent(llm)
        result = await agent.process_task(
            "Ransomware detected on 5 workstations in finance department"
        )
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_receive_message(self):
        agent = IncidentResponderAgent(FakeLLM())
        msg = AgentMessage(sender="supervisor", receiver="incident_responder", task="Contain ransomware outbreak")
        reply = await agent.receive(msg)
        assert reply.status == "completed"
        assert reply.receiver == "supervisor"

    @pytest.mark.asyncio
    async def test_system_prompt_includes_nist(self):
        agent = IncidentResponderAgent(FakeLLM())
        assert "NIST" in agent.system_prompt or "containment" in agent.system_prompt


# ---------------------------------------------------------------------------
# Workflow tests
# ---------------------------------------------------------------------------

from agents.registry import AgentRegistry
from agents.supervisor import SupervisorAgent
from workflows.soc_incident_response import run_soc_incident_response


class TestSOCWorkflow:
    @pytest.mark.asyncio
    async def test_workflow_runs_with_registered_agents(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(AlertAnalystAgent(llm))
        registry.register(ThreatHunterAgent(llm))
        registry.register(MalwareAnalystAgent(llm))
        registry.register(IncidentResponderAgent(llm))
        supervisor = SupervisorAgent(llm, registry)

        result = await run_soc_incident_response(
            supervisor,
            alert_data="Alert: Ransomware detected on workstation WS-005",
        )

        assert "request" in result
        assert "final_response" in result
        assert "agent_results" in result
        assert len(result["agent_results"]) >= 4

    @pytest.mark.asyncio
    async def test_workflow_includes_all_soc_agents_in_request(self):
        llm = FakeLLM()
        registry = AgentRegistry()
        registry.register(AlertAnalystAgent(llm))
        registry.register(ThreatHunterAgent(llm))
        registry.register(MalwareAnalystAgent(llm))
        registry.register(IncidentResponderAgent(llm))
        supervisor = SupervisorAgent(llm, registry)

        result = await run_soc_incident_response(supervisor, "Test alert")
        assert "alert" in result["request"].lower() or "incident" in result["request"].lower()


# ---------------------------------------------------------------------------
# API registration tests
# ---------------------------------------------------------------------------

class TestAPIRegistration:
    def test_all_soc_agents_importable(self):
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set, skipping API registration test")
        from api.main import registry
        agent_names = list(registry.list_agents().keys())
        assert "alert_analyst" in agent_names
        assert "threat_hunter" in agent_names
        assert "malware_analyst" in agent_names
        assert "incident_responder" in agent_names

    def test_total_agent_count(self):
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set, skipping API registration test")
        from api.main import registry
        assert len(registry) >= 8  # original 4 + 4 SOC agents
