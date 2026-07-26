# Developer Guide

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 16 (optional — the app works without it for LLM-only tasks)

### Setup

```bash
# Clone and enter the project
cd agent_harness

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY

# Run the server
uvicorn api.main:app --reload
```

### Verify

```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"0.3.0","checks":{...}}

curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"input": "What is 2+2?"}'
# → {"task_id":"...","request":"...","analysis":"...","agent_results":[...],"final_response":"..."}
```

### Run Tests

```bash
python -m pytest tests/ -v
# → 147 passed
```

---

## Project Structure

```
agent_harness/
├── agents/              # AI agent implementations
│   ├── supervisor.py    # Central coordinator
│   ├── registry.py      # Agent name → instance lookup
│   ├── researcher.py    # Web research
│   ├── coder.py         # Code generation & testing
│   ├── security.py      # Vulnerability analysis
│   ├── qa.py            # Quality assurance
│   ├── alert_analyst.py # SOC alert triage
│   ├── threat_hunter.py # SOC threat hunting
│   ├── malware_analyst.py  # SOC malware analysis
│   └── incident_responder.py  # SOC incident response
│
├── api/                 # FastAPI HTTP layer
│   └── main.py          # Routes, middleware, auth, health
│
├── config/              # Configuration
│   └── settings.py      # Pydantic-settings (typed env vars)
│
├── core/                # Engine layer
│   ├── agent.py         # Agent runtime (7-phase lifecycle)
│   ├── specialized.py   # SpecializedAgent base class
│   ├── protocol.py      # AgentMessage dataclass
│   ├── memory.py        # Three-tier memory (Working/LongTerm/Vector)
│   ├── cache.py         # LLM response cache (LRU + TTL)
│   ├── security.py      # Auth, rate limiting, input validation
│   ├── middleware.py    # Request tracing, logging, error handling
│   └── monitoring.py    # Metrics, health checks
│
├── database/            # Persistence
│   ├── connection.py    # Async SQLAlchemy engine
│   └── models.py        # ORM models (TaskMemory, SolutionMemory, etc.)
│
├── models/              # Abstract interfaces
│   ├── llm.py           # LLM base + OpenAILLM
│   └── embeddings.py    # Embedder base + OpenAIEmbedder
│
├── soc/                 # SOC domain
│   ├── frameworks.py    # MITRE ATT&CK, Cyber Kill Chain, NIST CSF
│   └── models.py        # Alert, IOC, Incident dataclasses
│
├── tools/               # Capability library
│   ├── base.py          # BaseTool ABC
│   ├── registry.py      # ToolRegistry
│   ├── web_search.py    # DuckDuckGo search
│   ├── code_runner.py   # Sandboxed Python execution
│   ├── ioc_check.py     # IOC extraction via regex
│   └── log_parser.py    # Multi-format log parser
│
├── workflows/           # Multi-agent workflows
│   ├── soc_incident_response.py
│   └── security_audit.py
│
├── tests/               # 147 tests across 13 files
├── Dockerfile           # Multi-stage build
├── docker-compose.yml   # API + PostgreSQL
└── requirements.txt     # Python dependencies
```

---

## How to Add a New Agent

### Step 1: Create the agent file

Create `agents/my_agent.py`:

```python
"""
My Agent.

Purpose: Describe what this agent does.
"""

import logging
from models.llm import LLM
from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.my_agent")

MY_AGENT_SYSTEM_PROMPT = """You are a [role description].

For each task:
1. Do step one
2. Do step two
3. Produce the required output

Output a structured report with:
- Section A
- Section B"""


class MyAgent(SpecializedAgent):
    """One-line description of what this agent does."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="my_agent",
            llm=llm,
            system_prompt=MY_AGENT_SYSTEM_PROMPT,
        )

    async def process_task(self, task: str) -> str:
        """
        Process a task and return a result string.

        Args:
            task: The input task description.

        Returns:
            The agent's output as a string.
        """
        logger.info("Processing: %.80s", task)

        messages = self._build_messages(
            f"Perform the task.\n\n--- Data ---\n{task}\n\n"
            f"Provide the expected output."
        )
        return await self._llm_chat(messages, temperature=0.3)
```

### Step 2: Register the agent in the API

In `api/main.py`, add an import and register it:

```python
from agents.my_agent import MyAgent

# After existing registrations...
registry.register(MyAgent(llm))
```

### Step 3 (optional): Wire into the Supervisor

The `SupervisorAgent` uses the `AgentRegistry` to discover agents. Since it reads `registry.list_agents()` dynamically, any registered agent is automatically available for dispatch. No supervisor changes are needed unless you want to force inclusion in certain workflows.

### Step 4: Write tests

Create `tests/test_my_agent.py`:

```python
"""Tests for MyAgent."""

import pytest
from models.llm import LLM, LLMResponse, LLMUsage
from core.protocol import AgentMessage
from agents.my_agent import MyAgent


class FakeLLM(LLM):
    """Deterministic LLM stub for testing."""

    def __init__(self, response: str = "analysis result"):
        self.response = response

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        return LLMResponse(content=self.response, usage=LLMUsage())


class TestMyAgent:
    @pytest.mark.asyncio
    async def test_agent_name(self):
        agent = MyAgent(llm=FakeLLM())
        assert agent.name == "my_agent"

    @pytest.mark.asyncio
    async def test_process_task_returns_output(self):
        agent = MyAgent(llm=FakeLLM("task output"))
        result = await agent.process_task("do something")
        assert "task output" in result

    @pytest.mark.asyncio
    async def test_receive_message(self):
        agent = MyAgent(llm=FakeLLM("reply text"))
        msg = AgentMessage(sender="supervisor", receiver="my_agent", task="test")
        reply = await agent.receive(msg)
        assert reply.status == "completed"
        assert "reply text" in reply.response

    @pytest.mark.asyncio
    async def test_receive_failure_returns_failed_status(self):
        class BrokenLLM(LLM):
            async def chat(self, **kwargs) -> LLMResponse:
                raise RuntimeError("LLM error")

        agent = MyAgent(llm=BrokenLLM())
        msg = AgentMessage(sender="supervisor", receiver="my_agent", task="test")
        reply = await agent.receive(msg)
        assert reply.status == "failed"
```

---

## How to Add a New Tool

### Step 1: Create the tool

Create `tools/my_tool.py`:

```python
"""
My tool.

Purpose: Describe what this tool does.
"""

from typing import Any
from tools.base import BaseTool


class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "The input to process"},
        },
        "required": ["input"],
    }

    async def execute(self, input: str = "", **kwargs) -> str:
        """Execute the tool logic."""
        return f"processed: {input}"
```

### Step 2: Register in the runtime

For the `Agent` runtime (auto tool selection):

```python
agent = Agent(llm=llm)
agent.tools.register(MyTool())
```

For the Supervisor (agents use tools directly), inject into the agent's constructor:

```python
class MyAgent(SpecializedAgent):
    def __init__(self, llm: LLM, my_tool=None):
        super().__init__(name="my_agent", llm=llm, system_prompt=...)
        self.my_tool = my_tool

    async def process_task(self, task: str) -> str:
        if self.my_tool:
            result = await self.my_tool(input=task)
        ...
```

---

## Coding Standards

### Docstrings

Every module, class, and public method must have a docstring. Module docstrings explain purpose and clean architecture layering:

```python
"""
Module name.

Purpose: What this module does and why it exists.

Clean architecture: What this module depends on and what depends on it.
"""
```

### Naming

| Convention | Example |
|-----------|---------|
| Files: `snake_case` | `alert_analyst.py` |
| Classes: `PascalCase` | `AlertAnalystAgent` |
| Methods/functions: `snake_case` | `process_task()`, `_build_messages()` |
| Constants: `UPPER_SNAKE_CASE` | `ALERT_ANALYST_PROMPT` |
| Private helpers: `_leading_underscore` | `_llm_chat()`, `_run_code_blocks()` |
| Async: `async def` prefix | `async def process_task()` |

### Imports

Order: standard library → third-party → project modules. One `from` per import group:

```python
import json
import logging
from typing import Optional

from models.llm import LLM
from core.specialized import SpecializedAgent
```

### Agent Pattern

Every agent follows this exact pattern:

1. **Module docstring** — purpose and capabilities
2. **System prompt constant** — `UPPER_SNAKE_CASE` string
3. **Class** — extends `SpecializedAgent`, docstring explains role
4. **`__init__`** — calls `super().__init__(name=, llm=, system_prompt=)`
5. **`process_task(self, task: str) -> str`** — the single public method
6. **Logging** — `logger.info()` at entry with `%.80s` truncation

```python
class MyAgent(SpecializedAgent):
    """One-line description."""

    def __init__(self, llm: LLM):
        super().__init__(name="my_agent", llm=llm, system_prompt=MY_PROMPT)

    async def process_task(self, task: str) -> str:
        logger.info("Processing: %.80s", task)
        messages = self._build_messages(f"...{task}...")
        return await self._llm_chat(messages, temperature=0.3)
```

### Tool Pattern

Every tool follows this exact pattern:

1. **Module docstring** — purpose
2. **Class** — extends `BaseTool`
3. **Class attributes** — `name`, `description`, `parameters`
4. **`async def execute(self, **kwargs) -> Any`** — the single public method

```python
class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something"
    parameters = {
        "type": "object",
        "properties": {"input": {"type": "string"}},
        "required": ["input"],
    }

    async def execute(self, input: str = "", **kwargs) -> str:
        return f"result: {input}"
```

### Error Handling

- **Agent errors** — raise `AgentError` subclasses (`TaskAnalysisError`, `PlanningError`, `ExecutionError`) for lifecycle failures. The `Agent` runtime catches these and produces a graceful error message.
- **Tool errors** — let exceptions propagate; the runtime wraps them in `ExecutionError`.
- **LLM errors** — `_safe_chat()` catches, logs, records in `state.errors`, and re-raises. The tenacity `@retry` decorator handles transient failures with exponential backoff.
- **Never** catch and silence without logging.

### Testing Standards

- **Never call a real LLM.** Use `FakeLLM` with deterministic responses.
- **Stub tools** via `FunctionTool` (wraps an async callable as a `BaseTool`).
- **Test the message protocol** — send `AgentMessage`, assert reply status and content.
- **Test failure paths** — broken LLM, missing tool, tool that raises.
- **Use `pytest.mark.asyncio`** for all async tests.

```python
class FakeLLM(LLM):
    """Deterministic LLM stub for testing."""

    def __init__(self, response: str = '{"goal": "test"}'):
        self.response = response

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        return LLMResponse(content=self.response, usage=LLMUsage())
```

### Configuration

- All environment-dependent values go in `config/settings.py` — never read `os.environ` directly.
- New settings must be added to `Settings` with a sensible default.
- Document new settings in `.env.example`.

### Logging

- Use `logging.getLogger(__name__)` at module level — the logger name follows the module path.
- `logger.info()` for normal operations (with `%.60s` truncation for user input).
- `logger.warning()` for recoverable issues.
- `logger.exception()` in exception handlers (includes traceback).
- Never use `print()`.

### Git Workflow

- No commits unless explicitly requested.
- Before committing: `git status`, `git diff`, `git log --oneline -10`.
- Write concise commit messages matching the repo style.
- Never force-push or amend commits.
