"""Tests for Multi-Agent CTF Team Collaboration Framework.

Covers:
  - SpecialistAgent creation and analysis
  - MalwareAnalysisAgent
  - WebSecurityAgent
  - CryptoAgent
  - ForensicsAgent
  - AgentFinding model
  - TeamMessage communication
  - EvidencePool deduplication and ranking
  - CoordinatorAgent classification and delegation
  - End-to-end team coordination workflow
  - SupervisorAgent backward compatibility
"""

import json
import pytest

from agents.team.evidence import AgentFinding, EvidencePool
from agents.team.communication import TeamMessage, MessageType
from agents.team.specialists import SpecialistAgent
from agents.team.specialists.malware_agent import MalwareAnalysisAgent
from agents.team.specialists.web_agent import WebSecurityAgent
from agents.team.specialists.crypto_agent import CryptoAgent
from agents.team.specialists.forensics_agent import ForensicsAgent
from agents.team.coordinator import CoordinatorAgent


# ===================================================================
# AgentFinding
# ===================================================================

class TestAgentFinding:
    def test_minimal_creation(self):
        f = AgentFinding(agent_name="test", findings=["found x"], evidence=["ev.png"])
        assert f.agent_name == "test"
        assert f.findings == ["found x"]
        assert f.evidence == ["ev.png"]
        assert f.confidence == 0.5
        assert f.tools_used == []

    def test_full_creation(self):
        f = AgentFinding(
            agent_name="malware_agent",
            findings=["PE detected", "IOC extracted"],
            evidence=["pe_header.txt", "ioc_list.txt"],
            confidence=0.85,
            tools_used=["file", "strings"],
            category="malware",
        )
        d = f.to_dict()
        assert d["agent_name"] == "malware_agent"
        assert len(d["findings"]) == 2
        assert d["confidence"] == 0.85

    def test_to_dict(self):
        f = AgentFinding(agent_name="a", findings=["f1"], evidence=["e1"], confidence=0.9, tools_used=["t1"], category="c")
        d = f.to_dict()
        assert d["agent_name"] == "a"
        assert d["category"] == "c"
        assert d["tools_used"] == ["t1"]


# ===================================================================
# TeamMessage
# ===================================================================

class TestTeamMessage:
    def test_task_message(self):
        msg = TeamMessage(type=MessageType.TASK, sender="coordinator", target="malware_agent", payload="Analyze sample")
        assert msg.type == MessageType.TASK
        assert msg.sender == "coordinator"
        assert msg.target == "malware_agent"
        assert msg.payload == "Analyze sample"
        assert msg.status == "pending"

    def test_finding_message(self):
        msg = TeamMessage(type=MessageType.FINDING, sender="malware_agent", target="coordinator",
                          payload="PE file detected", evidence=["headers.txt"], confidence=0.9, status="completed")
        assert msg.type == MessageType.FINDING
        assert msg.evidence == ["headers.txt"]
        assert msg.confidence == 0.9

    def test_message_types(self):
        assert MessageType.TASK.value == "TASK"
        assert MessageType.FINDING.value == "FINDING"
        assert MessageType.STATUS.value == "STATUS"
        assert MessageType.EVIDENCE.value == "EVIDENCE"

    def test_timestamp_set(self):
        msg = TeamMessage(type=MessageType.STATUS, sender="a", target="b")
        assert msg.timestamp is not None
        assert "T" in msg.timestamp


# ===================================================================
# EvidencePool
# ===================================================================

class TestEvidencePool:
    def test_empty_pool(self):
        pool = EvidencePool()
        assert len(pool) == 0
        assert pool.get_all() == []
        assert pool.get_ranked() == []

    def test_add_finding(self):
        pool = EvidencePool()
        f = AgentFinding(agent_name="a1", findings=["found x"], evidence=["e1"], confidence=0.8)
        pool.add_finding(f)
        assert len(pool) == 1

    def test_add_findings_bulk(self):
        pool = EvidencePool()
        f1 = AgentFinding(agent_name="a1", findings=["f1"], evidence=["e1"], confidence=0.7)
        f2 = AgentFinding(agent_name="a2", findings=["f2"], evidence=["e2"], confidence=0.9)
        pool.add_findings([f1, f2])
        assert len(pool) == 2

    def test_skips_empty_finding(self):
        pool = EvidencePool()
        f = AgentFinding(agent_name="a1", findings=[], evidence=[], confidence=0.5)
        pool.add_finding(f)
        assert len(pool) == 0

    def test_deduplicates_similar(self):
        pool = EvidencePool()
        f1 = AgentFinding(agent_name="a1", findings=["malware found"], evidence=["e1"], confidence=0.7)
        f2 = AgentFinding(agent_name="a2", findings=["malware found", "IOC extracted"], evidence=["e2"], confidence=0.9)
        pool.add_finding(f1)
        pool.add_finding(f2)
        assert len(pool) == 1
        assert pool.get_all()[0].agent_name == "a2"

    def test_keeps_different_findings(self):
        pool = EvidencePool()
        f1 = AgentFinding(agent_name="a1", findings=["malware found"], evidence=["e1"], confidence=0.7)
        f2 = AgentFinding(agent_name="a2", findings=["web vulnerability"], evidence=["e2"], confidence=0.9)
        pool.add_finding(f1)
        pool.add_finding(f2)
        assert len(pool) == 2

    def test_ranked_by_confidence(self):
        pool = EvidencePool()
        pool.add_finding(AgentFinding("a1", ["f1"], ["e1"], confidence=0.5))
        pool.add_finding(AgentFinding("a2", ["f2"], ["e2"], confidence=0.9))
        pool.add_finding(AgentFinding("a3", ["f3"], ["e3"], confidence=0.7))
        ranked = pool.get_ranked()
        assert ranked[0].confidence == 0.9
        assert ranked[1].confidence == 0.7
        assert ranked[2].confidence == 0.5

    def test_high_confidence_filter(self):
        pool = EvidencePool()
        pool.add_finding(AgentFinding("a1", ["f1"], ["e1"], confidence=0.5))
        pool.add_finding(AgentFinding("a2", ["f2"], ["e2"], confidence=0.8))
        high = pool.get_high_confidence(threshold=0.7)
        assert len(high) == 1
        assert high[0].agent_name == "a2"

    def test_consolidated_report(self):
        pool = EvidencePool()
        pool.add_finding(AgentFinding("a1", ["malware found"], ["md5 hash"], confidence=0.9))
        pool.add_finding(AgentFinding("a2", ["web vuln"], ["http trace"], confidence=0.6))
        report = pool.get_consolidated_report()
        assert report["total_findings"] == 2
        assert "a1" in report["agents_contributing"]
        assert len(report["consolidated_evidence"]) == 2

    def test_clear(self):
        pool = EvidencePool()
        pool.add_finding(AgentFinding("a1", ["f1"], ["e1"], confidence=0.8))
        pool.clear()
        assert len(pool) == 0


# ===================================================================
# SpecialistAgent base
# ===================================================================

class TestSpecialistAgent:
    def test_base_raises_not_implemented(self):
        agent = SpecialistAgent()
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(agent.analyze("test task"))

    def test_receive_unknown_type(self):
        agent = SpecialistAgent()
        agent.name = "test_agent"

        async def run():
            msg = TeamMessage(type=MessageType.CANCEL, sender="coordinator", target="test_agent", payload="cancel")
            reply = await agent.receive_message(msg)
            return reply

        import asyncio
        reply = asyncio.run(run())
        assert reply.status == "failed"
        assert "Unknown" in reply.payload


# ===================================================================
# MalwareAnalysisAgent
# ===================================================================

class TestMalwareAnalysisAgent:
    @pytest.mark.asyncio
    async def test_pe_analysis(self):
        agent = MalwareAnalysisAgent()
        finding = await agent.analyze("Analyze suspicious PE file: malware.exe")
        assert "PE" in " ".join(finding.findings)
        assert len(finding.evidence) >= 1
        assert finding.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_ioc_extraction(self):
        agent = MalwareAnalysisAgent()
        finding = await agent.analyze("Extract IOCs from malware sample")
        assert any("IOC" in f for f in finding.findings)
        assert "strings" in finding.tools_used or "yara" in finding.tools_used

    @pytest.mark.asyncio
    async def test_packed_detection(self):
        agent = MalwareAnalysisAgent()
        finding = await agent.analyze("Analyze packed executable for hidden payload")
        assert any("packed" in f.lower() for f in finding.findings)

    @pytest.mark.asyncio
    async def test_general_analysis(self):
        agent = MalwareAnalysisAgent()
        finding = await agent.analyze("Analyze this file")
        assert len(finding.findings) >= 1

    @pytest.mark.asyncio
    async def test_category_and_capabilities(self):
        agent = MalwareAnalysisAgent()
        assert agent.category == "malware"
        assert "pe_analysis" in agent.capabilities
        assert "ioc_extraction" in agent.capabilities

    @pytest.mark.asyncio
    async def test_confidence_increases_with_findings(self):
        agent = MalwareAnalysisAgent()
        finding = await agent.analyze("Analyze PE file and extract IOCs and indicators from packed sample")
        assert finding.confidence > 0.5


# ===================================================================
# WebSecurityAgent
# ===================================================================

class TestWebSecurityAgent:
    @pytest.mark.asyncio
    async def test_http_analysis(self):
        agent = WebSecurityAgent()
        finding = await agent.analyze("Analyze HTTP traffic for vulnerabilities")
        assert any("HTTP" in f for f in finding.findings)

    @pytest.mark.asyncio
    async def test_sql_injection(self):
        agent = WebSecurityAgent()
        finding = await agent.analyze("Test for SQL injection on login page")
        assert any("SQL" in f for f in finding.findings)

    @pytest.mark.asyncio
    async def test_xss_detection(self):
        agent = WebSecurityAgent()
        finding = await agent.analyze("Check for XSS vectors in user input")
        assert any("XSS" in f or "Cross-site" in f for f in finding.findings)

    @pytest.mark.asyncio
    async def test_api_analysis(self):
        agent = WebSecurityAgent()
        finding = await agent.analyze("Analyze API endpoints for security issues")
        assert any("API" in f for f in finding.findings)

    @pytest.mark.asyncio
    async def test_general_analysis(self):
        agent = WebSecurityAgent()
        finding = await agent.analyze("Check web application security")
        assert len(finding.findings) >= 1
        assert "curl" in finding.tools_used

    @pytest.mark.asyncio
    async def test_category(self):
        agent = WebSecurityAgent()
        assert agent.category == "web"
        assert "http_analysis" in agent.capabilities
        assert "vulnerability_pattern_analysis" in agent.capabilities


# ===================================================================
# CryptoAgent
# ===================================================================

class TestCryptoAgent:
    @pytest.mark.asyncio
    async def test_base64_detection(self):
        agent = CryptoAgent()
        finding = await agent.analyze("Decode base64 encoded string")
        assert any("Base" in f for f in finding.findings)

    @pytest.mark.asyncio
    async def test_hash_analysis(self):
        agent = CryptoAgent()
        finding = await agent.analyze("Identify hash type: MD5 hash value found")
        assert any("hash" in f.lower() for f in finding.findings)

    @pytest.mark.asyncio
    async def test_rsa_analysis(self):
        agent = CryptoAgent()
        finding = await agent.analyze("Analyze RSA public key")
        assert any("RSA" in f for f in finding.findings)

    @pytest.mark.asyncio
    async def test_xor_detection(self):
        agent = CryptoAgent()
        finding = await agent.analyze("XOR-encoded data needs decryption")
        assert any("XOR" in f for f in finding.findings)

    @pytest.mark.asyncio
    async def test_hex_detection(self):
        agent = CryptoAgent()
        finding = await agent.analyze("Convert hex encoded data")
        assert any("Hex" in f for f in finding.findings)

    @pytest.mark.asyncio
    async def test_general_analysis(self):
        agent = CryptoAgent()
        finding = await agent.analyze("Analyze this crypto data")
        assert len(finding.findings) >= 1

    @pytest.mark.asyncio
    async def test_category(self):
        agent = CryptoAgent()
        assert agent.category == "crypto"
        assert "encoding_analysis" in agent.capabilities


# ===================================================================
# ForensicsAgent
# ===================================================================

class TestForensicsAgent:
    @pytest.mark.asyncio
    async def test_metadata_analysis(self):
        agent = ForensicsAgent()
        finding = await agent.analyze("Extract EXIF metadata from image file")
        assert any("metadata" in f.lower() for f in finding.findings)
        assert "exiftool" in finding.tools_used

    @pytest.mark.asyncio
    async def test_disk_image(self):
        agent = ForensicsAgent()
        finding = await agent.analyze("Analyze disk image for hidden data")
        assert any("disk" in f.lower() or "image" in f.lower() for f in finding.findings)
        assert "binwalk" in finding.tools_used or "python" in finding.tools_used

    @pytest.mark.asyncio
    async def test_stego_detection(self):
        agent = ForensicsAgent()
        finding = await agent.analyze("Check for steganography in image")
        assert any("steganography" in f.lower() or "hidden" in f.lower() for f in finding.findings)

    @pytest.mark.asyncio
    async def test_timeline(self):
        agent = ForensicsAgent()
        finding = await agent.analyze("Build timeline from file timestamps")
        assert any("timeline" in f.lower() for f in finding.findings)

    @pytest.mark.asyncio
    async def test_general_analysis(self):
        agent = ForensicsAgent()
        finding = await agent.analyze("Perform forensic analysis")
        assert len(finding.findings) >= 1

    @pytest.mark.asyncio
    async def test_category(self):
        agent = ForensicsAgent()
        assert agent.category == "forensics"
        assert "metadata_analysis" in agent.capabilities
        assert "evidence_discovery" in agent.capabilities


# ===================================================================
# CoordinatorAgent
# ===================================================================

class TestCoordinatorAgent:
    @pytest.mark.asyncio
    async def test_classify_malware(self):
        coordinator = CoordinatorAgent()
        categories = coordinator._classify("Analyze this malware executable for viruses")
        assert "malware" in categories

    @pytest.mark.asyncio
    async def test_classify_web(self):
        coordinator = CoordinatorAgent()
        categories = coordinator._classify("Check for SQL injection on the login endpoint")
        assert "web" in categories

    @pytest.mark.asyncio
    async def test_classify_crypto(self):
        coordinator = CoordinatorAgent()
        categories = coordinator._classify("Decrypt this base64 encoded RSA key")
        assert "crypto" in categories

    @pytest.mark.asyncio
    async def test_classify_forensics(self):
        coordinator = CoordinatorAgent()
        categories = coordinator._classify("Extract metadata and find hidden artifacts")
        assert "forensics" in categories

    @pytest.mark.asyncio
    async def test_classify_general_fallback(self):
        coordinator = CoordinatorAgent()
        categories = coordinator._classify("Do something generic")
        assert "general" in categories

    @pytest.mark.asyncio
    async def test_classify_returns_scores(self):
        coordinator = CoordinatorAgent()
        categories = coordinator._classify("Analyze malware and web traffic")
        assert "malware" in categories
        assert "web" in categories

    @pytest.mark.asyncio
    async def test_select_agents_by_category(self):
        coordinator = CoordinatorAgent()
        malware = MalwareAnalysisAgent()
        web = WebSecurityAgent()
        coordinator.register_specialists([malware, web])
        selected = coordinator._select_agents({"malware": 1.0})
        assert len(selected) == 1
        assert selected[0].name == "malware_analysis_agent"

    @pytest.mark.asyncio
    async def test_select_multiple_agents(self):
        coordinator = CoordinatorAgent()
        coordinator.register_specialists([
            MalwareAnalysisAgent(),
            WebSecurityAgent(),
            CryptoAgent(),
            ForensicsAgent(),
        ])
        selected = coordinator._select_agents({"malware": 0.5, "web": 0.5})
        assert len(selected) == 2
        names = [a.name for a in selected]
        assert "malware_analysis_agent" in names
        assert "web_security_agent" in names

    @pytest.mark.asyncio
    async def test_coordinate_with_all_specialists(self):
        coordinator = CoordinatorAgent()
        coordinator.register_specialists([
            MalwareAnalysisAgent(),
            WebSecurityAgent(),
            CryptoAgent(),
            ForensicsAgent(),
        ])
        result = await coordinator.coordinate("Analyze suspicious file with encoded strings")
        assert len(result["findings"]) >= 1
        assert len(result["categories_identified"]) >= 1
        assert result["consolidated"]["resolution"] in ("consensus", "single_agent")

    @pytest.mark.asyncio
    async def test_coordinate_with_context(self):
        coordinator = CoordinatorAgent()
        coordinator.register_specialist(MalwareAnalysisAgent())
        result = await coordinator.coordinate("Analyze PE file", context={"file_name": "malware.exe"})
        assert result["consolidated"] is not None

    @pytest.mark.asyncio
    async def test_empty_coordination(self):
        coordinator = CoordinatorAgent()
        result = await coordinator.coordinate("test")
        assert result["consolidated"]["resolution"] == "no_findings"

    @pytest.mark.asyncio
    async def test_register_specialist(self):
        coordinator = CoordinatorAgent()
        assert len(coordinator.specialists) == 0
        coordinator.register_specialist(MalwareAnalysisAgent())
        assert len(coordinator.specialists) == 1
        assert "malware_analysis_agent" in coordinator.specialists

    @pytest.mark.asyncio
    async def test_register_specialists_bulk(self):
        coordinator = CoordinatorAgent()
        coordinator.register_specialists([MalwareAnalysisAgent(), WebSecurityAgent()])
        assert len(coordinator.specialists) == 2

    @pytest.mark.asyncio
    async def test_delegate_collect_findings(self):
        coordinator = CoordinatorAgent()
        malware = MalwareAnalysisAgent()
        coordinator.register_specialist(malware)
        findings = await coordinator._delegate_and_collect(
            [malware], "Analyze PE file for malware"
        )
        assert len(findings) == 1
        assert findings[0].agent_name == "malware_analysis_agent"

    @pytest.mark.asyncio
    async def test_resolve_findings_consensus(self):
        coordinator = CoordinatorAgent()
        findings = [
            AgentFinding("a1", ["malware detected"], ["hash"], confidence=0.9, category="malware"),
            AgentFinding("a2", ["web vulnerability"], ["url"], confidence=0.7, category="web"),
        ]
        resolved = coordinator._resolve_findings(findings)
        assert resolved["resolution"] == "consensus"
        assert resolved["lead_agent"] == "a1"

    @pytest.mark.asyncio
    async def test_resolve_findings_single(self):
        coordinator = CoordinatorAgent()
        findings = [
            AgentFinding("a1", ["malware detected"], ["hash"], confidence=0.9, category="malware"),
        ]
        resolved = coordinator._resolve_findings(findings)
        assert resolved["resolution"] == "single_agent"


# ===================================================================
# SupervisorAgent Backward Compatibility
# ===================================================================

class TestBackwardCompatibility:
    """Verify that SupervisorAgent still works without coordinator."""

    @pytest.mark.asyncio
    async def test_supervisor_accepts_coordinator_param(self):
        """Coordinator param should be accepted without breaking existing constructors."""
        from agents.supervisor import SupervisorAgent
        import inspect
        sig = inspect.signature(SupervisorAgent.__init__)
        assert "coordinator" in sig.parameters
        assert sig.parameters["coordinator"].default is None

    @pytest.mark.asyncio
    async def test_supervisor_creates_without_coordinator(self):
        """Existing instantiation should work unchanged."""
        from unittest.mock import MagicMock
        from agents.supervisor import SupervisorAgent
        from agents.registry import AgentRegistry

        llm = MagicMock()
        registry = AgentRegistry()
        supervisor = SupervisorAgent(llm=llm, registry=registry)
        assert supervisor.coordinator is None
        assert supervisor.llm is llm

    @pytest.mark.asyncio
    async def test_supervisor_run_dict_includes_team_coordination(self):
        """Return dict should always have team_coordination key (None when unused)."""
        from unittest.mock import MagicMock, AsyncMock
        from agents.supervisor import SupervisorAgent
        from agents.registry import AgentRegistry

        llm = MagicMock()
        llm.chat = AsyncMock(return_value=MagicMock(content='{"analysis":"test","steps":[]}'))
        registry = AgentRegistry()
        supervisor = SupervisorAgent(llm=llm, registry=registry)
        result = await supervisor.run("test request")
        assert "team_coordination" in result
        assert result["team_coordination"] is None


# ===================================================================
# Integration: End-to-End Team Coordination
# ===================================================================

class TestIntegration:
    @pytest.mark.asyncio
    async def test_multi_category_workflow(self):
        coordinator = CoordinatorAgent()
        coordinator.register_specialists([
            MalwareAnalysisAgent(),
            WebSecurityAgent(),
            CryptoAgent(),
            ForensicsAgent(),
        ])
        result = await coordinator.coordinate(
            "Analyze suspicious file. It's a malware sample with encoded strings and web traffic."
        )
        assert len(result["agents_dispatched"]) >= 2
        assert len(result["findings"]) >= 2
        assert len(result["evidence_pool"]["consolidated_evidence"]) >= 1
        assert result["evidence_pool"]["total_findings"] >= 2

    @pytest.mark.asyncio
    async def test_single_specialist_workflow(self):
        coordinator = CoordinatorAgent()
        coordinator.register_specialist(MalwareAnalysisAgent())
        result = await coordinator.coordinate("Analyze this malware sample")
        assert len(result["agents_dispatched"]) == 1
        assert result["agents_dispatched"][0] == "malware_analysis_agent"
        assert result["consolidated"]["resolution"] == "single_agent"

    @pytest.mark.asyncio
    async def test_evidence_pool_integration(self):
        coordinator = CoordinatorAgent()
        coordinator.register_specialists([MalwareAnalysisAgent(), CryptoAgent()])
        result = await coordinator.coordinate("Analyze encoded strings in executable")
        report = result["evidence_pool"]
        assert report["total_findings"] >= 1
        assert len(report["agents_contributing"]) >= 1

    @pytest.mark.asyncio
    async def test_message_log(self):
        coordinator = CoordinatorAgent()
        coordinator.register_specialist(MalwareAnalysisAgent())
        result = await coordinator.coordinate("Analyze this")
        assert len(result["message_log"]) >= 2
        assert result["message_log"][0]["type"] == "TASK"
        assert result["message_log"][1]["type"] == "FINDING"
