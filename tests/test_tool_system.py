"""Tests for the CTF Tool Execution Framework.

Covers:
  - Tool discovery and validation
  - ToolDefinitionRegistry lookup and filtering
  - ToolSelector ranking and scoring
  - ToolExecutor execution, timeout, failure states
  - ExecutionPolicy security enforcement
  - Pipeline integration with ExecutionAgent
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
import yaml

from tools.execution.registry import ToolDefinitionRegistry, ToolDefinition
from tools.execution.selector import ToolSelector
from tools.execution.executor import ToolExecutor, ExecutionStatus
from tools.execution.policy import ExecutionPolicy

from models.llm import LLM, LLMResponse, LLMUsage
from agents.registry import AgentRegistry
from agents.supervisor import SupervisorAgent
from agents.verifier import VerificationAgent
from core.specialized import SpecializedAgent
from skills_engine.planner import PlanStep, SkillPlanner, TaskPlan
from skills_engine.execution import ExecutionAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tool_yaml(tmp_dir: Path, category: str, tools: list[dict]) -> Path:
    cat_dir = tmp_dir / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    path = cat_dir / "tool.yaml"
    with open(path, "w") as f:
        yaml.dump({"tools": tools}, f)
    return path


def make_valid_registry(tmp_dir: Path) -> Path:
    make_tool_yaml(tmp_dir, "file_analysis", [
        {
            "name": "strings",
            "description": "Extract strings from binary files",
            "category": "file_analysis",
            "purpose": "Find embedded text",
            "input_types": ["file_path"],
            "output_types": ["text"],
            "risk_level": "low",
            "execution_method": "subprocess",
            "command_template": 'strings "{file_path}"',
            "timeout_seconds": 30,
        },
        {
            "name": "file",
            "description": "Determine file type",
            "category": "file_analysis",
            "purpose": "Identify file format",
            "input_types": ["file_path"],
            "output_types": ["text"],
            "risk_level": "low",
            "execution_method": "subprocess",
            "command_template": 'file "{file_path}"',
            "timeout_seconds": 10,
        },
    ])
    make_tool_yaml(tmp_dir, "malware", [
        {
            "name": "yara",
            "description": "Pattern match against YARA rules",
            "category": "malware",
            "purpose": "Classify malware samples",
            "input_types": ["file_path", "rules"],
            "output_types": ["text"],
            "risk_level": "medium",
            "execution_method": "subprocess",
            "command_template": 'yara "{rules}" "{file_path}"',
            "timeout_seconds": 60,
        },
    ])
    make_tool_yaml(tmp_dir, "steganography", [
        {
            "name": "binwalk",
            "description": "Extract embedded files from firmware",
            "category": "steganography",
            "purpose": "Uncover hidden files",
            "input_types": ["file_path"],
            "output_types": ["text"],
            "risk_level": "low",
            "execution_method": "subprocess",
            "command_template": 'binwalk "{file_path}"',
            "timeout_seconds": 60,
        },
    ])
    return tmp_dir


# ===================================================================
# Tool Discovery
# ===================================================================

class TestToolDiscovery:
    def test_discovers_valid_tools(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            make_valid_registry(d)
            registry = ToolDefinitionRegistry(definitions_dir=str(d))
            tools = registry.discover()
            names = {t.name for t in tools}
            assert "strings" in names
            assert "file" in names
            assert "yara" in names
            assert "binwalk" in names
            assert len(tools) == 4

    def test_invalid_tool_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            make_valid_registry(d)
            make_tool_yaml(d, "bad", [
                {"description": "missing name field", "category": "bad"},
            ])
            registry = ToolDefinitionRegistry(definitions_dir=str(d))
            tools = registry.discover()
            names = {t.name for t in tools}
            assert "strings" in names
            assert len(tools) == 4

    def test_missing_directory_returns_empty(self):
        registry = ToolDefinitionRegistry(definitions_dir=r"C:\nonexistent_tool_dir")
        tools = registry.discover()
        assert tools == []

    def test_ignores_non_yaml_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / ".hidden").mkdir()
            make_valid_registry(d)
            registry = ToolDefinitionRegistry(definitions_dir=str(d))
            tools = registry.discover()
            assert len(tools) == 4


# ===================================================================
# Tool Registry
# ===================================================================

class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            make_valid_registry(d)
            reg = ToolDefinitionRegistry(definitions_dir=str(d))
            reg.discover()
            yield reg

    def test_lookup_works(self, registry):
        tool = registry.get_tool("strings")
        assert tool is not None
        assert tool.name == "strings"
        assert tool.category == "file_analysis"

    def test_lookup_missing_returns_none(self, registry):
        tool = registry.get_tool("nonexistent")
        assert tool is None

    def test_category_filtering(self, registry):
        tools = registry.get_tools(category="file_analysis")
        names = {t.name for t in tools}
        assert "strings" in names
        assert "file" in names
        assert "yara" not in names

    def test_category_filtering_all(self, registry):
        tools = registry.get_tools()
        assert len(tools) == 4

    def test_list_categories(self, registry):
        cats = registry.list_categories()
        assert "file_analysis" in cats
        assert "malware" in cats
        assert "steganography" in cats

    def test_contains(self, registry):
        assert "strings" in registry
        assert "nonexistent" not in registry

    def test_len(self, registry):
        assert len(registry) == 4


# ===================================================================
# Tool Selector
# ===================================================================

class TestToolSelector:
    @pytest.fixture
    def selector(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            make_valid_registry(d)
            reg = ToolDefinitionRegistry(definitions_dir=str(d))
            reg.discover()
            yield ToolSelector(reg)

    @pytest.mark.asyncio
    async def test_ranks_tools_by_relevance(self, selector):
        results = await selector.select(
            challenge_description="Extract strings from a suspicious Windows executable",
            limit=3,
        )
        assert len(results) >= 1
        # strings should rank highest for this query
        assert results[0]["name"] == "strings"
        assert results[0]["confidence"] > 0.0

    @pytest.mark.asyncio
    async def test_no_matching_tools_returns_empty(self, selector):
        results = await selector.select(
            challenge_description="zzz_nonexistent_galactic_analyzer",
            limit=3,
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_category_filter_in_selector(self, selector):
        results = await selector.select(
            challenge_description="malware analysis sample",
            category="file_analysis",
            limit=5,
        )
        assert all(r["category"] == "file_analysis" for r in results)

    @pytest.mark.asyncio
    async def test_required_capability_boosts_score(self, selector):
        results = await selector.select(
            challenge_description="analyze binary file",
            required_capability="strings",
            limit=5,
        )
        strings_result = [r for r in results if r["name"] == "strings"]
        assert len(strings_result) >= 1
        assert strings_result[0]["confidence"] > 0.3

    @pytest.mark.asyncio
    async def test_skill_context_boosts_score(self, selector):
        skills = [{"name": "file-analysis", "description": "Analyze file types", "tags": ["file", "binary"]}]
        with_skills = await selector.select(
            challenge_description="binary",
            selected_skills=skills,
            limit=5,
        )
        assert len(with_skills) >= 1

    @pytest.mark.asyncio
    async def test_confidence_is_between_zero_and_one(self, selector):
        results = await selector.select(
            challenge_description="analyze executable file",
            limit=5,
        )
        for r in results:
            assert 0.0 <= r["confidence"] <= 1.0


# ===================================================================
# Tool Executor
# ===================================================================

class TestToolExecutor:
    @pytest.fixture
    def executor(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            make_valid_registry(d)
            reg = ToolDefinitionRegistry(definitions_dir=str(d))
            reg.discover()
            policy = ExecutionPolicy(allowed_tools=["echo_test", "slow_tool", "fail_tool", "strings", "file"])
            yield ToolExecutor(reg, policy=policy)

    @pytest.mark.asyncio
    async def test_blocked_tool_rejected(self, executor):
        result = await executor.execute(tool_name="nonexistent_tool")
        assert result["status"] == ExecutionStatus.BLOCKED.value

    @pytest.mark.asyncio
    async def test_unregistered_tool_rejected(self, executor):
        executor.policy.allowed_tools.add("random_cmd")
        result = await executor.execute(tool_name="random_cmd")
        assert result["status"] == ExecutionStatus.TOOL_NOT_FOUND.value

    @pytest.mark.asyncio
    async def test_execution_log_is_recorded(self, executor):
        executor.policy.allowed_tools.add("strings")
        await executor.execute(tool_name="strings", params={"file_path": __file__})
        log = executor.get_execution_log()
        assert len(log) >= 1
        entry = log[0]
        assert "tool" in entry
        assert "status" in entry
        assert "duration" in entry

    @pytest.mark.asyncio
    async def test_clear_log(self, executor):
        executor.policy.allowed_tools.add("strings")
        await executor.execute(tool_name="strings", params={"file_path": __file__})
        assert len(executor.get_execution_log()) >= 1
        executor.clear_log()
        assert executor.get_execution_log() == []


# ===================================================================
# Execution Policy
# ===================================================================

class TestExecutionPolicy:
    def test_allows_approved_tool(self):
        policy = ExecutionPolicy(allowed_tools=["strings", "file"])
        ok, msg = policy.check_tool("strings")
        assert ok is True
        assert msg == ""

    def test_rejects_unknown_tool(self):
        policy = ExecutionPolicy(allowed_tools=["strings"])
        ok, msg = policy.check_tool("rm")
        assert ok is False
        assert "not in the allowed list" in msg

    def test_blocks_dangerous_command(self):
        policy = ExecutionPolicy()
        ok, msg = policy.check_command("rm -rf /")
        assert ok is False
        assert "blocked" in msg.lower()

    def test_blocks_sudo_command(self):
        policy = ExecutionPolicy()
        ok, msg = policy.check_command("sudo rm file")
        assert ok is False

    def test_allows_safe_command(self):
        policy = ExecutionPolicy()
        ok, msg = policy.check_command('strings "sample.exe"')
        assert ok is True

    def test_dynamic_allow_block(self):
        policy = ExecutionPolicy(allowed_tools=["a"])
        assert "a" in policy.get_allowed()
        policy.block_tool("a")
        assert "a" not in policy.get_allowed()
        policy.allow_tool("b")
        assert "b" in policy.get_allowed()

    def test_get_allowed_returns_sorted(self):
        policy = ExecutionPolicy(allowed_tools=["z", "a", "m"])
        assert policy.get_allowed() == ["a", "m", "z"]


# ===================================================================
# Pipeline Integration
# ===================================================================

class FakeLLM(LLM):
    def __init__(self):
        self.plan_response = json.dumps({
            "analysis": "Analyze the suspicious file using tools.",
            "steps": [
                {"agent": "analyst", "task": "Analyze the suspicious Windows executable for hidden strings and file type.", "depends_on": []},
            ],
        })
        self.synthesis_response = "Analysis complete. The file appears to be a Windows executable with embedded strings."

    async def chat(self, messages, **kwargs):
        user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
        is_planning = "synthesize" not in user_content.lower() and "agent results" not in user_content.lower()
        content = self.plan_response if is_planning else self.synthesis_response
        return LLMResponse(
            content=content,
            usage=LLMUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )


class AnalysisAgent(SpecializedAgent):
    def __init__(self, llm):
        super().__init__(name="analyst", llm=llm, system_prompt="You are a CTF analysis agent.")

    async def process_task(self, task: str) -> str:
        if "Tool Execution Evidence" in task:
            return "Evidence received. Analysis complete based on tool outputs. flag{tool_integrated}"
        return "Analysis complete. flag{analysis_done}"


class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_tool_selector_and_executor_wired_into_execution_agent(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            make_valid_registry(d)
            tool_reg = ToolDefinitionRegistry(definitions_dir=str(d))
            tool_reg.discover()
            tool_selector = ToolSelector(tool_reg)
            tool_executor = ToolExecutor(tool_reg)
            # Ensure registered tools are allowed
            for tool in tool_reg:
                tool_executor.policy.allow_tool(tool.name)

            llm = FakeLLM()
            agent_registry = AgentRegistry()
            agent_registry.register(AnalysisAgent(llm))
            planner = SkillPlanner(llm, agent_registry)
            execution_agent = ExecutionAgent(
                agent_registry,
                tool_selector=tool_selector,
                tool_executor=tool_executor,
            )
            verifier = VerificationAgent()
            supervisor = SupervisorAgent(
                llm, agent_registry,
                planner=planner,
                execution_agent=execution_agent,
                verifier=verifier,
            )

            result = await supervisor.run("Analyze the suspicious Windows executable.")
            assert "final_response" in result
            assert result["final_response"] != ""
            assert result["verification"] is not None

    @pytest.mark.asyncio
    async def test_execution_agent_works_without_tool_system(self):
        llm = FakeLLM()
        agent_registry = AgentRegistry()
        agent_registry.register(AnalysisAgent(llm))
        planner = SkillPlanner(llm, agent_registry)
        execution_agent = ExecutionAgent(agent_registry)
        supervisor = SupervisorAgent(
            llm, agent_registry,
            planner=planner,
            execution_agent=execution_agent,
        )

        result = await supervisor.run("Analyze the suspicious file.")
        assert "final_response" in result

    @pytest.mark.asyncio
    async def test_tool_evidence_appended_to_agent_task(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            make_valid_registry(d)
            tool_reg = ToolDefinitionRegistry(definitions_dir=str(d))
            tool_reg.discover()
            tool_selector = ToolSelector(tool_reg)
            tool_executor = ToolExecutor(tool_reg)
            for tool in tool_reg:
                tool_executor.policy.allow_tool(tool.name)

            llm = FakeLLM()
            agent_registry = AgentRegistry()
            agent = AnalysisAgent(llm)
            agent_registry.register(agent)
            planner = SkillPlanner(llm, agent_registry)
            execution_agent = ExecutionAgent(
                agent_registry,
                tool_selector=tool_selector,
                tool_executor=tool_executor,
            )
            supervisor = SupervisorAgent(
                llm, agent_registry,
                planner=planner,
                execution_agent=execution_agent,
            )

            result = await supervisor.run(
                "Analyze the suspicious Windows executable for hidden strings."
            )
            assert "final_response" in result

    @pytest.mark.asyncio
    async def test_full_pipeline_contract_preserved_with_tools(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            make_valid_registry(d)
            tool_reg = ToolDefinitionRegistry(definitions_dir=str(d))
            tool_reg.discover()
            tool_selector = ToolSelector(tool_reg)
            tool_executor = ToolExecutor(tool_reg)
            for tool in tool_reg:
                tool_executor.policy.allow_tool(tool.name)

            llm = FakeLLM()
            agent_registry = AgentRegistry()
            agent_registry.register(AnalysisAgent(llm))
            planner = SkillPlanner(llm, agent_registry)
            execution_agent = ExecutionAgent(
                agent_registry,
                tool_selector=tool_selector,
                tool_executor=tool_executor,
            )
            verifier = VerificationAgent()
            supervisor = SupervisorAgent(
                llm, agent_registry,
                planner=planner,
                execution_agent=execution_agent,
                verifier=verifier,
            )

            result = await supervisor.run("Analyze file.")
            expected_keys = {
                "request", "analysis", "plan", "agent_results",
                "verification", "learning_report", "final_response",
                "flag_verification", "challenge",
                "team_coordination",
            }
            assert set(result.keys()) == expected_keys


# ===================================================================
# Security Tests
# ===================================================================

class TestSecurity:
    def test_rejects_arbitrary_command(self):
        policy = ExecutionPolicy(allowed_tools=["safe_tool"])
        ok, msg = policy.check_tool("rm")
        assert ok is False

    def test_rejects_dangerous_patterns(self):
        policy = ExecutionPolicy(allowed_tools=["test"])
        patterns = [
            "rm -rf /",
            "mkfs.ext4 /dev/sda",
            "dd if=/dev/zero of=/dev/sda",
            "sudo apt-get install",
            "chmod 777 /etc/passwd",
            "shutdown -h now",
        ]
        for cmd in patterns:
            ok, msg = policy.check_command(cmd)
            assert ok is False, f"Command not blocked: {cmd}"

    def test_allows_safe_tools(self):
        policy = ExecutionPolicy(allowed_tools=["strings", "file", "exiftool"])
        for tool in ["strings", "file", "exiftool"]:
            ok, msg = policy.check_tool(tool)
            assert ok is True, f"Safe tool blocked: {tool}"

    def test_security_no_false_positives_for_safe_commands(self):
        policy = ExecutionPolicy()
        safe = [
            'strings "sample.exe"',
            'file "/path/to/file"',
            'exiftool "image.jpg"',
            'yara "rules.yar" "sample.exe"',
            'binwalk "firmware.bin"',
        ]
        for cmd in safe:
            ok, msg = policy.check_command(cmd)
            assert ok is True, f"Safe command blocked: {cmd} ({msg})"
