# Skill Development Guide

This guide explains how to create, test, and integrate new cybersecurity
skill packs into the Agent Harness.

---

## Overview

A **Skill Pack** is a structured directory of knowledge that teaches an
AI agent how to approach a specific category of CTF or cybersecurity
challenge. The system discovers skill packs automatically from the
`skill_packs/` directory.

### Skill Lifecycle

```
Create skill pack directory
    ↓
Write skill.yaml (required metadata)
    ↓
Write knowledge.md (domain expertise)
    ↓
(Optional) Write tools.yaml, prompts/
    ↓
SkillPackLoader discovers and validates
    ↓
SkillRegistry indexes the pack
    ↓
SkillSelector ranks by context + filters
    ↓
SkillContextBuilder builds optimized prompt
    ↓
SkillInjector delivers to agent
```

---

## Directory Structure

Each skill pack lives in its own subdirectory under `skill_packs/`:

```
skill_packs/
    your_skill_name/
        skill.yaml          # Required: metadata
        README.md           # Recommended: overview
        knowledge.md        # Recommended: domain knowledge
        tools.yaml          # Optional: tool definitions
        prompts/            # Optional: prompt templates
            analysis_prompt.md
```

### Naming Convention

Use lowercase with hyphens: `web-security`, `malware-analysis`, `crypto-attacks`.

---

## skill.yaml Reference

This is the only required file. It defines the skill pack's metadata.

### Required Fields

```yaml
name: web-security
description: >-
  A concise description of what this skill covers. Used for search ranking
  and selection matching.

category: web
```

### Optional Fields

```yaml
difficulty: beginner
# One of: beginner, intermediate, advanced, expert

supported_challenges:
  - SQL injection detection
  - XSS exploitation
  - JWT manipulation

required_tools:
  - curl
  - sqlmap
  - jwt_tool

verification_methods:
  - Vulnerability reproduced with proof-of-concept
  - Flag extracted and verified
  - Remediation recommendation provided

tags:
  - web
  - owasp
  - sqli
  - xss
```

### Difficulty Levels

| Level | Description | Example |
|-------|-------------|---------|
| `beginner` | Fundamental concepts, single-step challenges | Basic SQL injection, steganography |
| `intermediate` | Multi-step analysis, requires tool use | RSA attacks, memory forensics |
| `advanced` | Complex scenarios, chained exploits | ROP chains, full malware unpacking |
| `expert` | Research-level, custom tooling | Novel crypto attacks, 0-day analysis |

---

## knowledge.md

Contains the domain expertise the agent should reference. Structure it
with clear headings:

```markdown
# Skill Name Knowledge Base

## Topic One
- Key concept
- Detection method
- Common tools

## Topic Two
- Step-by-step workflow
- Red flags

## Verification Criteria
- What constitutes a solved challenge
- Required output format
```

---

## tools.yaml

Defines tools associated with this skill. The agent uses this to
understand available tooling:

```yaml
tools:
  - name: tcpdump
    description: Capture and analyse network traffic
    usage: tcpdump [options] -i <interface>
    common_options:
      - "-i eth0: specify interface"
      - "-w file.pcap: write to file"
      - "-r file.pcap: read from file"
```

---

## Creating a New Skill Pack: Step by Step

### Step 1: Create the directory

```bash
mkdir skill_packs/my-new-skill
```

### Step 2: Write skill.yaml

```yaml
name: my-new-skill
description: >-
  My new cybersecurity skill for analysing XYZ challenges.
category: misc
difficulty: beginner
tags:
  - misc
  - new-skill
```

### Step 3: Add domain knowledge

Create `knowledge.md` with the technical content the agent needs:

```markdown
# My New Skill Knowledge

## Key Concepts
- Concept A: explanation
- Concept B: explanation

## Detection
How to identify this type of challenge.

## Workflow
1. First step
2. Second step
3. Capture flag
```

### Step 4: Test discovery

```python
from skills_engine.pack_loader import SkillPackLoader

loader = SkillPackLoader("skill_packs")
packs = loader.load_all()
for p in packs:
    print(p["frontmatter"]["name"])
```

### Step 5: Verify selection

```python
from skills_engine.registry import SkillRegistry
from skills_engine.selector import SkillSelector

registry = SkillRegistry()
for pack in loader.load_all():
    registry.register(pack)

selector = SkillSelector(registry)
selected = await selector.select(
    "my challenge description",
    category="misc",
    limit=3,
)
```

---

## Best Practices

1. **Keep knowledge focused** — Each skill pack should cover one category
   (web, crypto, forensics, etc.). Avoid creating "jumbo" packs.

2. **Educational content only** — All content must be defensive/educational.
   No instructions for illegal activities.

3. **Verification methods** — Always specify how to verify the challenge
   is solved. This feeds into the LearningReportGenerator.

4. **Write for agents, not humans** — Use clear, structured markdown
   that an LLM can parse efficiently. Bullet points and numbered lists
   work better than prose paragraphs.

5. **Token budget awareness** — Keep total content under ~2000 tokens
   per skill pack. The SkillContextBuilder will truncate if needed.

6. **Cross-reference sparingly** — Avoid requiring skills unless the
   dependency is strict. Prefer self-contained packs.

---

## Testing Your Skill Pack

Run the existing test suite to verify no regressions:

```bash
pytest tests/test_skill_system.py -v
```

For manual testing:

```python
from skills_engine.pack_loader import SkillPackLoader
from skills_engine.context import SkillContextBuilder

loader = SkillPackLoader("skill_packs")
packs = loader.load_all()
builder = SkillContextBuilder()
context = builder.build_context([p["frontmatter"] for p in packs])
print(context[:500])
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Skill not discovered | Missing `skill.yaml` | Create `skill.yaml` with required fields |
| Skill not loading | Missing `name` or `description` | Add required fields to `skill.yaml` |
| Seldom selected | Wrong category or tags | Update `category` and `tags` to match challenge patterns |
| Context too long | Knowledge content too verbose | Trim `knowledge.md` to essential concepts |
| Tool not recognised | Tool not in allowed list | Add to `required_tools` in `skill.yaml` |
