# CTF Challenge Development Guide

## Overview

The Challenge Orchestration and Evaluation Framework provides a structured way to package, validate, execute, and evaluate cybersecurity CTF challenges.

### Architecture

```
Challenge Package (challenge.yaml + files + hints)
    ↓
ChallengeLoader → ChallengeValidator
    ↓
ChallengeRegistry (search/filter by category, difficulty, skill)
    ↓
SupervisorAgent (pipeline: Phase 0 Load → Execute → Flag Verify)
    ↓
FlagVerifier (exact / regex / evidence match)
    ↓
LearningReportGenerator (challenge info + flag result + tools used)
```

## Challenge Package Structure

```
challenges/
    <challenge_id>/
        challenge.yaml        # Required: metadata and configuration
        README.md             # Recommended: description and learning objectives
        files/                # Optional: challenge files (images, binaries, logs)
        hints/                # Optional: hint text files
        expected/
            flag.txt          # Expected flag for verification
```

## challenge.yaml Format

```yaml
name: StegoRSA Beginner Challenge
category: steganography
difficulty: beginner
description: >
  Extract hidden information from the provided image using steganography tools.
required_skills:
  - steganography-basics
  - cryptography
allowed_tools:
  - exiftool
  - binwalk
  - strings
verification:
  type: exact_flag
flag_format: CTF{.*}
expected_flag: CTF{hidden_in_plain_sight}
```

### Required Fields

| Field | Description |
|-------|-------------|
| `name` | Human-readable challenge name |
| `category` | One of: `steganography`, `malware`, `cryptography`, `web_security`, `forensics`, `general` |
| `difficulty` | One of: `beginner`, `intermediate`, `advanced`, `expert` |
| `description` | Challenge description provided to the agent |
| `expected_flag` | The correct flag value for verification |

### Optional Fields

| Field | Default | Description |
|-------|---------|-------------|
| `required_skills` | `[]` | Skills needed to solve the challenge |
| `allowed_tools` | `[]` | Tools permitted for the challenge |
| `verification` | `{"type": "exact_flag"}` | Verification method |
| `flag_format` | `""` | Regex pattern for flag format |

## Verification Methods

### 1. Exact Match (`exact_flag`)

The agent response must contain the exact expected flag string.

```yaml
verification:
  type: exact_flag
expected_flag: CTF{hello_world}
```

### 2. Regex Match (`regex`)

The flag is extracted using the `flag_format` regex pattern, then compared.

```yaml
verification:
  type: regex
flag_format: CTF\{.*\}
expected_flag: CTF{abc123}
```

### 3. Evidence-Based (`evidence`)

Checks tool outputs and agent responses for the expected flag.

```yaml
verification:
  type: evidence
expected_flag: CTF{hidden_flag}
```

## Creating a New Challenge

1. Create a challenge directory: `challenges/<challenge_id>/`
2. Create `challenge.yaml` with required fields
3. Add challenge files to `files/` directory
4. Add hints to `hints/` directory (optional)
5. Add `expected/flag.txt` with the correct flag
6. Create `README.md` with learning objectives
7. Validate: `pytest tests/test_challenge_system.py::TestChallengeValidation`

### Example: Beginner Steganography

```
challenges/stego_basic_001/
    challenge.yaml        # name, category, difficulty, etc.
    README.md             # Learning objectives
    files/
        screenshot.png    # Image with hidden data
    hints/
        hint_01.txt       # "Try running strings on the image"
    expected/
        flag.txt          # CTF{hidden_in_plain_sight}
```

## Student Learning Objectives

When creating challenges, consider:

- **Steganography**: File metadata analysis, data hiding, encoding detection
- **Malware**: Binary analysis, string extraction, IOC identification
- **Cryptography**: Key strength analysis, algorithm identification, cryptanalysis
- **Web Security**: HTTP analysis, parameter manipulation, injection patterns
- **Forensics**: Artifact recovery, timeline analysis, metadata examination

## Pipeline Integration

The challenge system integrates as an optional pre-processing step:

```python
supervisor = SupervisorAgent(
    llm, registry,
    planner=planner,
    execution_agent=execution_agent,
    challenge_loader=ChallengeLoader(),
    flag_verifier=FlagVerifier(),
)

result = await supervisor.run(
    "Solve this challenge.",
    challenge_id="stego_basic_001",
)
```

When `challenge_id` is provided, the pipeline becomes:

```
Phase 0: Load & Validate Challenge
    ↓
Phase 1: Analyse & Plan (with challenge context)
    ↓
Phase 2: Execute Plan (skills + tools + agents)
    ↓
Phase 3: Verify Results
    ↓
Phase 4: Flag Verification
    ↓
Phase 5: Learning Report (with challenge/tool/flag evaluation)
    ↓
Phase 6: Synthesize Final Response
```
