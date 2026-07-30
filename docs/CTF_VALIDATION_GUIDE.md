# CTF Validation & Optimization Framework

## Overview

The Validation & Optimization Framework evaluates the AI Agent Harness against real-world CTF challenges. It provides model comparison, strategy optimization, failure-driven improvement, and automated performance reporting.

### Architecture

```
External CTF Datasets (benchmark/datasets/external/)
  |-- CTFSourceRegistry (track challenge provenance)
  |-- DatasetLoader (load YAML catalogs)
  |
Model Registry (models/*.yaml)
  |-- ModelConfig (name, provider, model_id, temperature, tools)
  |-- ModelRegistry (discover, lookup by ID/name)
  |
ModelBenchmarkRunner
  |-- Run same challenges across multiple model configs
  |-- Produce ModelBenchmarkResult per challenge
  |
ComparisonEngine
  |-- Compare model performance side-by-side
  |-- Generate ComparisonReport with rankings
  |
HardModeController
  |-- Adaptive strategy rotation for hard challenges
  |-- 6 strategies: default → change_agent → add_skills → different_tools → decompose → alternative
  |
AgentDebate
  |-- Specialist agents submit arguments
  |-- Resolve conflicting findings via confidence-weighted consensus
  |
OptimizationEngine
  |-- Aggregate metrics + failure analysis
  |-- Generate OptimizationReport with capability-by-category breakdowns
  |
Memory (enhanced)
  |-- StrategyMemory: successful + failed approaches per category
  |-- Category patterns: what to do + what to avoid
```

## New Components

### CTFSourceRegistry

Tracks challenge provenance:

```python
from benchmark_engine import CTFSourceRegistry

reg = CTFSourceRegistry()
reg.list_sources()
# {"educational_ctf": "Educational CTF Collection", ...}

reg.get("picoctf")
# {"name": "picoCTF", "type": "competition", "license": "educational", ...}

reg.register("my_ctf", {"name": "My CTF", "type": "private", "license": "proprietary"})
```

6 built-in sources: educational_ctf, picoctf, cryptohack, hackthebox, tryhackme, rootme

### Model Registry

Load model configurations from `models/*.yaml`:

```python
from models import ModelRegistry

reg = ModelRegistry()
reg.list_models()
# ["DeepSeek V4 Flash Free", "Claude 4 Sonnet", "Grok 3", "Kimi K2"]

config = reg.get("deepseek-v4-flash-free")
print(config.name, config.provider, config.temperature)
# DeepSeek V4 Flash Free DeepSeek 0.3
```

Creating a new model profile:

```yaml
# models/my_model.yaml
name: My Custom Model
provider: Custom
model_id: custom-model-v1
temperature: 0.5
max_tokens: 4096
available_tools:
  - python
  - strings
  - curl
notes: Custom model with specific tuning
```

### ModelBenchmarkRunner

Run the same challenges against different model configurations:

```python
from benchmark_engine import ModelBenchmarkRunner, DatasetLoader

ds = DatasetLoader()
challenge_ids = ds.get_challenge_ids("external_medium")

runner = ModelBenchmarkRunner()

# Run one model
results = await runner.run_model("deepseek-v4-flash-free", challenge_ids)

# Run multiple models for comparison
all_results = await runner.run_models(
    ["deepseek-v4-flash-free", "claude-sonnet-4-20250514"],
    challenge_ids,
)

# Get per-model metrics
mc = runner.get_model_metrics("deepseek-v4-flash-free")
print(mc.success_rate)
```

### ComparisonEngine

Compare model performance:

```python
from benchmark_engine import ComparisonEngine

engine = ComparisonEngine()
engine.add_model_results("model_a", results_a)
engine.add_model_results("model_b", results_b)

report = engine.compare(dataset_name="medium_crypto")
print(report.summary_table())
print(report.to_json())
```

Example output:

```
══════════════════════════════════════════════════════════════════
Model Comparison Report: medium_crypto
══════════════════════════════════════════════════════════════════
Model                          Attempted   Solved     Rate    Conf     Time
──────────────────────────────────────────────────────────────────────────────
DeepSeek V4 Flash Free                10        8   80.0%    0.87    5.2s
Claude 4 Sonnet                       10        7   70.0%    0.82    6.1s
──────────────────────────────────────────────────────────────────────────────
Best Model: DeepSeek V4 Flash Free (80.0%)
══════════════════════════════════════════════════════════════════
```

### HardModeController

Adaptive strategy for difficult challenges:

```python
from benchmark_engine import HardModeController

ctrl = HardModeController(max_attempts=5)

for attempt in range(5):
    strategy = ctrl.get_strategy("hard_challenge_001")
    print(f"Attempt {attempt + 1}: {strategy['strategy']}")

    result = await solve_challenge(strategy)
    outcome = ctrl.register_outcome("hard_challenge_001", result)

    if result.solved:
        print("Solved!")
        break
```

Strategies cycle through: default → change_agent_selection → add_skills_context → use_different_tools → decompose_problem → try_alternative_approach

### AgentDebate

Resolve conflicting specialist findings:

```python
from agents.team.debate import AgentDebate, DebateArgument
from agents.team.evidence import AgentFinding

debate = AgentDebate()

# Submit arguments directly
debate.submit_argument(
    "crypto_challenge",
    DebateArgument("crypto_agent", "RSA small exponent attack",
                   evidence=["key.pub"], confidence=0.9)
)

# Or from AgentFinding
finding = AgentFinding("crypto_agent", ["RSA weak key"], ["key.pub"], confidence=0.85)
debate.submit_finding("crypto_challenge", finding)

# Resolve
consensus = debate.resolve("crypto_challenge")
print(consensus.consensus)       # "RSA weak key"
print(consensus.confidence)      # 0.9
print(consensus.dissenting_opinions)  # conflicting positions
```

### OptimizationEngine & Report

Generate comprehensive capability assessment:

```python
from benchmark_engine import OptimizationEngine, MetricsCollector

engine = OptimizationEngine(metrics=metrics_collector)
report = engine.generate(dataset_name="validation_run")

print(report.summary_table())
# ══════════════════════════════════════════════════════════════════
# Optimization Report: validation_run
# ══════════════════════════════════════════════════════════════════
#   Overall Success Rate: 62.5%
#   Total Challenges:     16
#
# Capability by Category:
#   crypto          [################....] 80%  (4/5)
#   web             [###############.....] 75%  (3/4)
#   malware         [########............] 40%  (2/5)
#   forensics       [##########..........] 50%  (1/2)
#
# Weakest Area:  malware (40%)
# Strongest Area: crypto (80%)
#
# Improvement Actions:
#   - Improve malware capability (40% success). Common failures: missing_skill.
#   - -> Add skills for malware challenges. Review skill registry for gaps.
# ══════════════════════════════════════════════════════════════════

# JSON export
json_str = report.to_json()
```

## Enhanced Memory

StrategyMemory now stores both successful and failed approaches:

```python
from memory.strategies import StrategyMemory

mem = StrategyMemory()

# Record successful strategies
mem.record("crypto", "Check RSA parameters before brute force", confidence=0.85)

# Record failed approaches to avoid
mem.record_failed("crypto", "Start with brute force factorization",
                   failure_reason="Too many possibilities")

# Get category patterns (what to do + what to avoid)
patterns = mem.get_category_patterns("crypto")
# {
#   "category": "crypto",
#   "successful_approaches": ["Check RSA parameters before brute force"],
#   "failed_approaches": ["Start with brute force factorization"],
#   "avoid_strategies": ["AVOID: Start with brute force factorization"],
# }
```

## Datasets

### External CTF Datasets

Located in `benchmark/datasets/external/`:

| File | Challenges | Difficulty | Categories |
|------|-----------|-----------|-----------|
| `medium.yaml` | 10 | medium | crypto(3), web(3), malware(2), forensics(2) |
| `hard.yaml` | 20 | hard | crypto(5), web(5), malware(5), forensics(5) |
| `ctf_sources.yaml` | — | metadata | source definitions |

```python
from benchmark_engine import DatasetLoader

ds = DatasetLoader(datasets_dir="benchmark/datasets/external")
ds.list_datasets()       # ["hard", "medium"]
ds.get_challenge_ids("hard")  # 20 challenge IDs
ds.get_categories("hard")     # {"crypto": [...], "web": [...], ...}
```

## Adding External Challenges

1. Add metadata to `benchmark/datasets/external/ctf_sources.yaml` if from a new source
2. Add challenge definition to the appropriate difficulty YAML file
3. Optionally register the source with `CTFSourceRegistry`

```yaml
# In benchmark/datasets/external/hard.yaml
challenges:
  - id: ext_crypto_hard_006
    name: New Crypto Challenge
    category: crypto
    difficulty: hard
    description: "Challenge description here"
    required_skills: ["cryptography-advanced", "specific-skill"]
    allowed_tools: ["python"]
    expected_flag: CTF{new_flag}
```

## Workflow: Full Validation Run

```python
from benchmark_engine import (
    DatasetLoader, ModelBenchmarkRunner, ComparisonEngine, OptimizationEngine
)

# 1. Load dataset
ds = DatasetLoader(datasets_dir="benchmark/datasets/external")
challenge_ids = ds.get_challenge_ids("medium")

# 2. Run models
runner = ModelBenchmarkRunner()
all_results = await runner.run_models(
    ["deepseek-v4-flash-free", "claude-sonnet-4-20250514"],
    challenge_ids,
)

# 3. Compare
engine = ComparisonEngine()
for mid, results in all_results.items():
    engine.add_model_results(mid, results)
comparison = engine.compare(dataset_name="external_medium")

# 4. Optimize
opt = OptimizationEngine(metrics=runner.get_model_metrics("deepseek-v4-flash-free"))
report = opt.generate(dataset_name="external_medium", model_comparison=comparison)

print(report.summary_table())
```

## Testing

```bash
python -m pytest tests/test_ctf_validation_system.py -v
```

58 tests covering:
- CTFSourceRegistry (7 tests)
- ModelConfig / ModelRegistry (5 tests)
- ModelBenchmarkRunner (5 tests)
- ComparisonEngine (5 tests)
- HardModeController (7 tests)
- AgentDebate (7 tests)
- Enhanced StrategyMemory (4 tests)
- OptimizationReport / OptimizationEngine (7 tests)
- External datasets (5 tests)
- Backward compatibility (2 tests)
