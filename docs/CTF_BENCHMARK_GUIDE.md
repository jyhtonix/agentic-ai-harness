# CTF Benchmarking & Autonomous Improvement Framework

## Overview

The Benchmark Framework measures how effectively the Agentic CTF Harness solves real cybersecurity challenges. It tracks success rates, execution performance, agent effectiveness, and failure patterns to drive autonomous improvement.

### Architecture

```
BenchmarkRunner
  |-- loads challenge definitions (ChallengeLoader + DatasetLoader)
  |-- executes SupervisorAgent (with optional retry)
  |-- collects BenchmarkResult
  |
MetricsCollector
  |-- aggregates results across runs
  |-- per-category, per-difficulty, per-agent breakdowns
  |
FailureAnalyzer
  |-- classifies failures (missing_skill, wrong_agent, etc.)
  |-- generates improvement recommendations
  |
AgentMetricsTracker
  |-- tracks per-agent success rates and confidence
  |
RetryController
  |-- manages adaptive retry with strategy changes
  |
Evaluator
  |-- produces BenchmarkReport with summary table + JSON
  |
BenchmarkHistory
  |-- persists results to disk for trend analysis
  |
Memory System
  |-- StrategyMemory (successful approaches per category)
  |-- FailureMemory (failure patterns & recommendations)
  |-- SolutionMemory (approaches, tools, agents per challenge)
```

## Quick Start

```python
from challenges_engine.loader import ChallengeLoader
from benchmark_engine import BenchmarkRunner, Evaluator
from agents.supervisor import SupervisorAgent

# Setup
loader = ChallengeLoader()
supervisor = SupervisorAgent(llm=llm, registry=registry)

# Create benchmark runner
runner = BenchmarkRunner(
    challenge_loader=loader,
    supervisor_factory=lambda: supervisor.run("Solve challenge", challenge_id=cid),
)

# Run a single challenge
result = runner.run_challenge("crypto_medium_001")
print(f"Solved: {result.solved}, Time: {result.execution_time}s")

# Run a dataset
results = runner.run_dataset([
    "crypto_medium_001", "crypto_medium_002",
    "web_medium_001", "web_medium_002",
])

# Generate report
evaluator = Evaluator(metrics=runner.metrics)
report = evaluator.generate_report(dataset_name="medium_run")
print(report.summary_table())
print(report.to_json())
```

## BenchmarkRunner

The `BenchmarkRunner` is the main entry point. It:

1. Loads a challenge via `ChallengeLoader`
2. Creates a supervisor via the factory function
3. Runs the challenge (with retry support)
4. Extracts metrics from the supervisor result
5. Saves history
6. Returns a `BenchmarkResult`

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `challenge_loader` | ChallengeLoader | default loader | Loads challenge definitions |
| `supervisor_factory` | callable | None | Async callable returning supervisor result dict |
| `retry_controller` | RetryController | default (3 attempts) | Controls retry behaviour |
| `failure_analyzer` | FailureAnalyzer | default | Classifies failures |
| `history` | BenchmarkHistory | default (file storage) | Persists results |

## Key Components

### BenchmarkResult

| Field | Type | Description |
|-------|------|-------------|
| `challenge_id` | str | Unique challenge identifier |
| `category` | str | Challenge category (crypto, web, malware, forensics) |
| `difficulty` | str | Difficulty level |
| `status` | str | solved / failed / timeout / error / partial |
| `flag_result` | str | PASS / FAIL / None |
| `execution_time` | float | Wall-clock time in seconds |
| `confidence` | float | Verification confidence (0.0—1.0) |
| `attempts` | int | Number of attempts taken |
| `tools_used` | list[str] | Tools invoked during solve |
| `agents_used` | list[str] | Agents involved in solve |
| `failure_reason` | str | Reason for failure (if failed) |
| `failure_category` | str | Classified failure type |
| `solved` | bool | True if status == "solved" |

### MetricsCollector

Aggregates `BenchmarkResult` instances:

```python
mc = MetricsCollector()
mc.record(result)
mc.record_many(results)

print(mc.total)          # Total challenges
print(mc.solved)         # Solved count
print(mc.success_rate)   # Success ratio
print(mc.by_category())  # Per-category breakdown
print(mc.by_difficulty())# Per-difficulty breakdown
print(mc.agent_metrics())# Per-agent stats
print(mc.tool_usage())   # Tool frequency
print(mc.failure_breakdown())  # Failure type distribution
```

### FailureAnalyzer

Classifies failures into categories:
- `missing_skill` — agent lacks required skill
- `wrong_agent` — incorrect specialist selected
- `insufficient_reasoning` — analysis quality too low
- `missing_tool` — required tool unavailable
- `verification_failure` — flag format or content mismatch
- `timeout` — execution exceeded time limit
- `runtime_error` — unexpected exception

```python
fa = FailureAnalyzer()
analysis = fa.analyze(result)
# {
#   "category": "missing_skill",
#   "reason": "No matching skill found for AES analysis",
#   "recommendation": "Add skills for crypto challenges...",
#   "confidence_weight": 0.8
# }
```

### RetryController

Manages multiple attempts with strategy adaptation:

```python
rc = RetryController(max_attempts=5)
rc.register_failure("challenge_id", analysis)
strategy = rc.get_strategy("challenge_id", current_attempt)
# {
#   "action": "retry",
#   "attempt": 2,
#   "category": "missing_skill",
#   "strategy": "Add relevant skill context...",
#   "recommendation": "..."
# }
```

### AgentMetricsTracker

Tracks per-agent performance:

```python
tracker = AgentMetricsTracker()
tracker.record("crypto_agent", solved=True, confidence=0.85, category="crypto", tools_used=["python"])
tracker.record("malware_agent", solved=False, confidence=0.3, category="malware")

print(tracker.get("crypto_agent").success_rate)      # 1.0
print(tracker.get_weakest())                          # "malware_agent"
print(tracker.get_strongest())                        # "crypto_agent"
print(tracker.all())                                  # dict of all agents
```

### Evaluator and BenchmarkReport

Generates comprehensive reports:

```python
evaluator = Evaluator(metrics=metrics_collector)
report = evaluator.generate_report(dataset_name="my_benchmark")

# Text summary
print(report.summary_table())
# ════════════════════════════════════════════
# CTF Benchmark Report: my_benchmark
# ════════════════════════════════════════════
#   Total Challenges:  50
#   Solved:            34
#   Success Rate:      68.0%
#   ...
# Weakest Area: malware (50.0%)
# Recommendations:
#   - Improve malware category...
# ════════════════════════════════════════════

# JSON export
json_str = report.to_json()
```

## Memory Systems

Three persistent memory stores for autonomous improvement:

### StrategyMemory

Stores successful strategies per category:

```python
mem = StrategyMemory()
mem.record("crypto", "Try RSA small exponent analysis first", confidence=0.85)
best = mem.get_best("crypto")
strategies = mem.get_strategies("crypto")
```

### FailureMemory

Records failure patterns:

```python
mem = FailureMemory()
mem.record("crypto_001", "crypto", "wrong key size", "missing_skill", "Add RSA skill")
common = mem.get_common_failures(top_n=5)
recs = mem.get_recommendations()
```

### SolutionMemory

Stores solution approaches:

```python
mem = SolutionMemory()
mem.record("crypto_001", "crypto", "medium", "small exponent attack",
           tools_used=["python"], agents_used=["crypto_agent"], success=True)
approaches = mem.get_successful_approaches("crypto")
```

## Dataset System

The `DatasetLoader` reads benchmark datasets from `benchmark/datasets/*.yaml`:

```python
from benchmark_engine import DatasetLoader

loader = DatasetLoader()
datasets = loader.list_datasets()  # ["medium"]
challenges = loader.load_dataset("medium")  # 20 challenge definitions
ids = loader.get_challenge_ids("medium")    # ["crypto_medium_001", ...]
cats = loader.get_categories("medium")      # {"crypto": [...], "web": [...], ...}
```

### Adding New Challenges

1. Create challenge file in `challenges/` (standard `challenge.yaml` format)
2. Add entry to `benchmark/datasets/medium.yaml` (or create a new dataset YAML)
3. Set `difficulty: medium` (or beginner/hard)
4. Define `expected_flag` for verification

### Creating a New Dataset

```yaml
# benchmark/datasets/hard.yaml
dataset: hard
description: "Hard difficulty CTF challenges"
version: "1.0"
challenges:
  - id: crypto_hard_001
    name: ...
    category: crypto
    difficulty: hard
    description: "..."
    required_skills: [...]
    allowed_tools: [...]
    expected_flag: CTF{...}
```

## Interpreting Results

### Success Rate by Category

| Rate | Meaning |
|------|---------|
| > 80% | Strong coverage — domain is well understood |
| 50-80% | Adequate — some skill gaps remain |
| < 50% | Weak — needs new skills/tools/agents |

### Common Failure Patterns

| Failure | Likely Cause | Fix |
|---------|-------------|-----|
| missing_skill | Skill registry missing domain knowledge | Add skill definitions |
| wrong_agent | Coordinator misclassifies problem | Improve classification keywords |
| insufficient_reasoning | Agent lacks domain context | Enhance system prompts |
| missing_tool | Tool not in registry or blocked | Add tool definition / adjust policy |
| verification_failure | Expected flag mismatch | Verify expected_flag value |

## Autonomous Improvement Loop

The framework supports a closed improvement loop:

1. **Benchmark** — Run dataset, collect results
2. **Analyze** — Identify failure patterns and weak agents
3. **Recommend** — Generate improvement suggestions
4. **Update** — Add missing skills, tools, or adjust agents
5. **Re-benchmark** — Verify improvement by re-running

Example:

```python
runner = BenchmarkRunner(loader, supervisor_factory)
results = await runner.run_dataset(dataset_ids)
evaluator = Evaluator(metrics=runner.metrics)
report = evaluator.generate_report()

print(report.summary_table())
print("Recommendations:", report.recommendations)

# Store successful strategies
for r in results:
    if r.solved:
        strategy_mem.record(r.category, r.agents_used[0], confidence=r.confidence)
    else:
        failure_mem.record(r.challenge_id, r.category, r.failure_reason,
                          r.failure_category, "Improve coverage")
```

## Testing

```bash
python -m pytest tests/test_benchmark_system.py -v
```

78 tests covering:
- BenchmarkResult model (5 tests)
- MetricsCollector aggregation (8 tests)
- BenchmarkRunner (7 tests)
- FailureAnalyzer (6 tests)
- RetryController (7 tests)
- AgentMetricsTracker (6 tests)
- Evaluator / BenchmarkReport (7 tests)
- Memory systems (11 tests)
- DatasetLoader (5 tests)
- History (5 tests)
- End-to-end workflows (3 tests)
