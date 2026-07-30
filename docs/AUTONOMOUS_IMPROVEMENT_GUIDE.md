# Autonomous CTF Reasoning & Self-Improvement Guide

## Overview

Phase 3.9 introduces an autonomous reasoning and self-improvement layer that enables the agent harness to:

1. **Analyze** challenges before execution to determine optimal strategy
2. **Detect skill gaps** from failed attempts
3. **Propose and evolve strategies** based on historical outcomes
4. **Rank strategies** by proven success rate
5. **Retry with enhanced phases** when standard retry fails
6. **Learn continuously** from every result
7. **Compete autonomously** in CTF-style competitions
8. **Report improvements** over time

The framework is fully backward compatible — existing code using `RetryController` without `use_enhanced=True` behaves exactly as before.

---

## Architecture

```
                      ┌─────────────────────┐
                      │  ChallengeAnalyzer   │  Pre-execution analysis
                      │     Agent            │
                      └──────────┬──────────┘
                                 │ classification
                                 ▼
┌───────────────────────────────────────────────────────────┐
│                    Execution Phase                         │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              RetryController (enhanced)              │  │
│  │  1. normal_execution                                 │  │
│  │  2. change_strategy                                  │  │
│  │  3. change_agent_assignment                          │  │
│  │  4. agent_debate                                     │  │
│  │  5. generate_new_hypothesis                          │  │
│  │  6. execute_improved_plan                             │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────┬────────────────────────────────────┘
                       │ result
                       ▼
┌───────────────────────────────────────────────────────────┐
│               AutonomousLearner                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │FeedbackCollect│  │SkillGapDetect│  │KnowledgeUpdater   │ │
│  │              │  │              │  │                   │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │StrategyEvolut│  │StrategyRanker│  │SkillImprovement   │ │
│  │Engine        │  │              │  │Proposal           │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
└──────────────────────┬────────────────────────────────────┘
                       │ updates
                       ▼
┌───────────────────────────────────────────────────────────┐
│                 Knowledge & Memory Stores                  │
│  Strategy Memory  │  Solution Memory  │  Failure Memory   │
│  Skill Proposals  │  Update History   │  Feedback         │
└───────────────────────────────────────────────────────────┘
                       │
                       ▼
               ┌───────────────────┐
               │ CompetitionRunner  │  CTF competition mode
               │ Scorer / Leaderboa │
               └───────────────────┘
                       │
                       ▼
               ┌───────────────────┐
               │Improvement Report │  Phase-over-phase delta
               │Generator          │
               └───────────────────┘
```

---

## Components

### 1. ChallengeAnalyzerAgent

Pre-execution analysis that classifies a challenge by category, complexity, required agents, recommended tools, and strategy.

```python
from agents.team.challenge_analyzer import ChallengeAnalyzerAgent

result = ChallengeAnalyzerAgent.analyze(
    "Crypto challenge with RSA and padding oracle",
    required_skills=["crypto-basics"]
)
# Returns: {
#   "category": ["crypto"],
#   "complexity": "high",
#   "is_multi_stage": True,
#   "required_agents": ["CryptoAgent", "WebAgent"],
#   "recommended_tools": ["python", "openssl", "rsatool"],
#   "recommended_strategy": "Cryptanalysis Strategy",
#   "required_skills": ["crypto-basics"]
# }
```

#### Classification Categories
| Category       | Keywords                           |
|----------------|------------------------------------|
| crypto         | rsa, aes, decrypt, cipher, xor     |
| web            | sql, xss, injection, login, http   |
| malware        | malware, pe, shellcode, unpack     |
| forensics      | forensics, metadata, hidden, pcap  |
| binary         | binary, buffer, overflow, rop      |
| reverse        | reverse, decompile, obfuscate      |
| general        | (default fallback)                 |

#### Complexity Levels
- **low**: single keyword match, ≤2 domain keywords
- **medium**: 2–3 domain keywords or multi-stage indicators
- **high**: 4+ keywords, obfuscation, multi-stage, or complex language

### 2. StrategyEvolutionEngine

Evolves and refines strategies based on historical results — successful and failed.

```python
from benchmark_engine.strategy_evolution import StrategyEvolutionEngine

engine = StrategyEvolutionEngine()
evolved = engine.evolve("crypto", benchmark_results)
# Returns list of strategy statements

strategy_text = engine.evolve_strategy_text("crypto", results)
# Returns formatted strategy block
```

- Successful results produce refined strategies (e.g., "Continue using python")
- Failed results produce corrective strategies (e.g., "Avoid missing PE analysis — install pefile")
- Works per-category; results filtered by category

### 3. SkillGapDetector

Analyzes failed benchmark results and identifies missing skills across 5 categories × 5 skills.

```python
from benchmark_engine.skill_gap import SkillGapDetector

detector = SkillGapDetector()

result = detector.analyze(benchmark_result)
# Returns {"gaps": [...], "confidence": 0.85}

summary = detector.get_summary()
top_gaps = detector.get_top_gaps(5)
```

#### Category-to-Skill Mapping
| Category  | Skills                                                |
|-----------|-------------------------------------------------------|
| crypto    | rsa, aes, xor, hash, padding                         |
| malware   | pe, shellcode, obfuscation, packer, dynamic-analysis |
| web       | sql-injection, xss, csrf, ssrf, auth-bypass          |
| binary    | buffer-overflow, rop, format-string, ret2libc, canary |
| forensics | file-carving, metadata, stego, memory-analysis, pcap |

A gap requires: `failure_category == "missing_skill"` AND a keyword match in the failure reason.

### 4. SkillImprovementProposal

Generates human-readable skill improvement proposals from detected gaps.

```python
from skills_engine.improvement import SkillImprovementProposal

proposer = SkillImprovementProposal()

proposal = proposer.generate("pe-analysis", "malware", confidence=0.85)
# Returns structured proposal with urgency, description, template

proposals = proposer.generate_batch([{"gap": ..., "category": ..., "occurrences": ...}])
report = proposer.format_report()
```

Each proposal includes a template for a new exercise challenge in the format: `Challenge: {name}: {description}`.

### 5. StrategyRanker

Ranks strategies by their historical success rate with persistent storage.

```python
from memory.strategy_ranker import StrategyRanker

ranker = StrategyRanker(storage_dir="data/strategy_ranker")

ranked = ranker.rank("crypto")         # sorted by score desc
best = ranker.get_best("crypto")       # top strategy text
top = ranker.get_top_n("crypto", 3)    # top N dicts

ranker.record_outcome("crypto", "Check RSA params", success=True)
rate = ranker.get_success_rate("crypto", "Check RSA params")
report = ranker.get_ranked_report("crypto")
```

Success rates are computed as `wins / (wins + losses)`.

### 6. Enhanced RetryController

Extends the existing RetryController with 6-phase retry pipeline (disabled by default for backward compatibility).

```python
from benchmark_engine.retry import RetryController

# Standard mode (unchanged)
ctrl = RetryController(max_attempts=3)
ctrl.register_failure("c1", analysis)
strategy = ctrl.get_strategy("c1", attempt=2)  # No "phase" key

# Enhanced mode
ctrl = RetryController(max_attempts=6, use_enhanced=True)
ctrl.register_failure("c1", analysis)
strategy = ctrl.get_strategy("c1", attempt=2)
# Returns: {"action": "retry", "phase": "change_strategy", ...}
```

#### Six Enhancement Phases
| Attempt | Phase                    | Behavior                                   |
|---------|--------------------------|--------------------------------------------|
| 1       | normal_execution         | Standard retry                             |
| 2       | change_strategy          | Switch strategy based on analysis          |
| 3       | change_agent_assignment  | Reassign agents                            |
| 4       | agent_debate             | Trigger agent debate for new approach      |
| 5       | generate_new_hypothesis  | Generate fresh hypothesis                  |
| 6+      | execute_improved_plan    | Execute with full improvement context      |

### 7. AutonomousLearner

Orchestrates learning from benchmark results — detects gaps, evolves strategies, updates memory.

```python
from learning_engine import AutonomousLearner

learner = AutonomousLearner()

# Single result
entry = learner.learn_from_result(benchmark_result)

# Batch
entries = learner.learn_from_results([result1, result2])

# Summary
summary = learner.get_improvement_summary()
# {
#   "total_challenges_processed": 10,
#   ...
# }
```

The learner coordinates:
1. **FeedbackCollector** — stores feedback entries with notes
2. **SkillGapDetector** — identifies missing skills
3. **KnowledgeUpdater** — evolves strategies, generates skill proposals, updates memory

### 8. FeedbackCollector

Stores and queries feedback entries.

```python
from learning_engine import FeedbackCollector

fc = FeedbackCollector()
fc.collect(benchmark_result, notes="Slow but correct")
feedback = fc.get_feedback(category="crypto", status="solved")
summary = fc.get_summary()  # {total, solved, failed, categories}
fc.clear()
```

### 9. KnowledgeUpdater

Processes learning entries and updates memory stores.

```python
from learning_engine import KnowledgeUpdater

updater = KnowledgeUpdater()
result = updater.update_from_learning({
    "challenge_id": "...",
    "status": "failed",
    "actions_taken": ["detected_skill_gaps", "evolved_strategy"],
    "skill_gaps": {"gaps": ["pe-analysis"], "confidence": 0.85},
    "evolved_strategy": ["Use PE analysis tools"],
})
# Returns {"updates": ["strategy_memory_evolved", "skill_proposal_created"]}

proposals = updater.get_skill_proposals()
history = updater.get_update_history()
```

### 10. Competition Runner

Runs autonomous CTF competitions with scoring and leaderboards.

```python
from competition import CompetitionRunner, Scorer, ScoreEntry, Leaderboard

# Runner
async def run():
    async def challenge_runner(challenge_id: str) -> BenchmarkResult:
        ...
    runner = CompetitionRunner(challenge_runner=challenge_runner)
    result = await runner.run_competition(["c1", "c2", "c3"], "MyTeam")

# Scorer
scorer = Scorer()
entry = scorer.calculate_score("MyTeam", results, total_time=150.0)

# Leaderboard
lb = Leaderboard(storage_dir="data/leaderboard")
lb.record(entry)
rankings = lb.get_rankings()
team = lb.get_team("MyTeam")
```

#### CompetitionConfig
| Parameter                    | Default | Description                          |
|------------------------------|---------|--------------------------------------|
| max_attempts_per_challenge   | 3       | Retries per challenge                |
| time_limit_seconds           | 3600    | Total competition time limit         |
| track_leaderboard            | True    | Auto-record to leaderboard           |
| points_per_difficulty        | {...}   | Points for easy/medium/hard          |

### 11. ImprovementReportGenerator

Generates phase-over-phase improvement reports.

```python
from benchmark_engine.improvement_report import ImprovementReportGenerator

generator = ImprovementReportGenerator()

report = generator.generate(
    previous_metrics=previous_metrics_collector,
    current_metrics=current_metrics_collector
)

print(report.summary_table())
print(report.to_dict())
```

Report fields: `previous_success_rate`, `current_success_rate`, `improvement_delta`, `improvements_made`, `timestamp`.

---

## Backward Compatibility

All existing APIs remain unchanged:

- `RetryController()` without arguments still works as before (no phase tracking)
- `StrategyMemory`, `MetricsCollector`, and all Phase 3.7/3.8 classes unchanged
- `BenchmarkResult` schema unchanged
- All 708+ existing tests continue to pass

---

## Test Suite

```bash
# Run all autonomous learning tests
pytest tests/test_autonomous_learning.py -v

# Run full regression
pytest tests/ -v
```

Expected: 60+ new tests, 0 regressions.
