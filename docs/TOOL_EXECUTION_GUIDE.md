# CTF Tool Execution Framework

## Overview

The Tool Execution Framework provides a controlled, auditable, and safe mechanism for the AI agent to discover, select, and execute approved cybersecurity command-line tools during CTF challenge resolution.

### Architecture

```
ToolDefinitionRegistry (YAML-backed metadata)
    |
    v
ToolSelector (keyword + capability scoring)
    |
    v
ExecutionPolicy (allow/block lists + pattern blocking)
    |
    v
ToolExecutor (subprocess with timeout + audit log)
    |
    v
ExecutionAgent (tool evidence appended to agent tasks)
```

### Components

| Component | File | Purpose |
|-----------|------|---------|
| ToolDefinitionRegistry | `tools/execution/registry.py` | Discovers, validates, and provides lookup for tool definitions from YAML files |
| ToolSelector | `tools/execution/selector.py` | Ranks tools by relevance to challenge description, skills, and required capabilities |
| ToolExecutor | `tools/execution/executor.py` | Executes tool commands via subprocess with timeout and status tracking |
| ExecutionPolicy | `tools/execution/policy.py` | Security layer — allowlist, blocklist, dangerous pattern detection |

## Tool Metadata Format

Tool definitions live in `tools/execution/definitions/<category>/tool.yaml`.

```yaml
tools:
  - name: strings
    description: Extract readable ASCII and Unicode strings from binary files
    category: file_analysis
    purpose: Discover embedded text, configuration data, and hidden messages in binaries
    input_types:
      - file_path
    output_types:
      - text
    risk_level: low
    execution_method: subprocess
    command_template: 'strings "{file_path}"'
    timeout_seconds: 30
```

### Required Fields

| Field | Description |
|-------|-------------|
| `name` | Unique tool identifier (used for allowlist matching) |
| `description` | Human-readable description of what the tool does |
| `category` | Must match one of the category subdirectories |

### Optional Fields

| Field | Default | Description |
|-------|---------|-------------|
| `purpose` | "" | Specific CTF/analysis use case |
| `input_types` | [] | Types of inputs the tool accepts |
| `output_types` | [] | Types of outputs the tool produces |
| `risk_level` | "low" | Security classification (low/medium/high) |
| `execution_method` | "subprocess" | How the tool is executed |
| `command_template` | "" | Python format string for subprocess invocation |
| `timeout_seconds` | 30 | Maximum execution time before TIMEOUT |

### Adding a New Tool

1. Create `tools/execution/definitions/<category>/tool.yaml`
2. Add a tool entry with required fields (name, description, category)
3. Add the tool name to `ExecutionPolicy.allowed_tools`
4. Run `pytest tests/test_tool_system.py` to verify discovery

## Execution Lifecycle

```
1. ToolSelector.select(challenge_description, skills, capability)
       ↓
2. Ranked list of recommended tools with confidence scores
       ↓
3. ToolExecutor.execute(tool_name, params)
       ↓
4. ExecutionPolicy.check_tool() → check_command()
       ↓
5. subprocess with timeout (asyncio.create_subprocess_shell)
       ↓
6. Execution result: {status, output, error, duration}
       ↓
7. Evidence appended to agent task via ExecutionAgent
```

### Execution Statuses

| Status | Meaning |
|--------|---------|
| `SUCCESS` | Command completed with exit code 0 |
| `FAILED` | Command completed with non-zero exit code |
| `TIMEOUT` | Command exceeded timeout_seconds |
| `BLOCKED` | Rejected by ExecutionPolicy (tool or command pattern blocked) |
| `TOOL_NOT_FOUND` | Tool not registered in ToolDefinitionRegistry or binary not found |

## Security Model

### ExecutionPolicy Controls

- **Tool allowlist**: Only tools in `allowed_tools` can execute
- **Command pattern blocking**: Dangerous shell patterns (`rm -rf`, `sudo`, `dd if=`, etc.) are rejected before execution
- **Timeouts**: Every execution has a configurable timeout (default 30s)
- **No unrestricted shell**: Commands are built from templates with parameter substitution — no ad-hoc shell execution
- **Audit log**: All execution attempts (including blocked) are recorded with timestamps and duration

### Default Blocked Patterns

```
rm -rf, mkfs, dd if=, > /dev/, shutdown, reboot,
sudo, su, chmod 777, chown, passwd, useradd, deluser,
iptables, route, ifconfig, wget, curl -o, nc -e, ncat -e,
nmap, hydra, john, hashcat, aircrack, metasploit, msfvenom
```

## Pipeline Integration

The tool system integrates into the existing pipeline as an optional extension to `ExecutionAgent`:

```python
execution_agent = ExecutionAgent(
    registry=agent_registry,
    tool_selector=ToolSelector(tool_registry),
    tool_executor=ToolExecutor(tool_registry),
)
```

When wired, the execution flow becomes:

```
PlanStep
    ↓
Skill Selection (if skill_selector available)
    ↓
Tool Selection (if tool_selector + tool_executor available)
    ↓
Tool Execution → Evidence Collection
    ↓
Agent Dispatch (task includes tool evidence)
```

Both `tool_selector` and `tool_executor` are optional — omitting them preserves the original pipeline behavior without modification.

## Current Tool Definitions

| Category | Tools |
|----------|-------|
| file_analysis | file, strings, exiftool |
| malware | yara, capa |
| steganography | binwalk |
| web | curl |
| general | python |
