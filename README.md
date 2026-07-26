# AI Agent Harness

A production-ready multi-agent orchestration framework.

## Architecture

```
User Input → Orchestrator → Planner → Executor(s) → Reviewer → Response
```

### Layers
- **api/** — FastAPI HTTP entry point
- **core/** — Orchestration engine & agent lifecycle
- **agents/** — Specialized agent implementations
- **tools/** — Capabilities (filesystem, web, code)
- **models/** — LLM & embedding interfaces
- **database/** — Persistence layer
- **config/** — Environment & runtime configuration

## Quick Start
```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn api.main:app --reload
```
