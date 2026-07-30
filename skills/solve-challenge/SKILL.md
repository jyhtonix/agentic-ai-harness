---
name: solve-challenge
description: >-
  Master orchestrator for solving CTF challenges. Analyses challenge files,
  determines the category, routes to the appropriate category skill,
  and guides the agent through discovery, exploitation, and flag capture.
domain: ctf
subdomain: general
category: master
tags: [ctf, orchestrator, solve, triage]
version: "1.0"
author: "agent-harness"
user_invocable: true
argument-hint: "[challenge_directory]"
allowed-tools: [Bash, Read, Write, Glob, Grep, Task, WebFetch, WebSearch]
requires: [ctf-web, ctf-forensics, ctf-reverse]
token_budget:
  frontmatter: 150
  full_content: 1800
---

## When to Use

When the user provides a CTF challenge directory or description and asks to solve it, find the flag, or analyse the challenge.

## Prerequisites

- Challenge directory exists under `challenges/`
- Relevant category skill is available (`/ctf-web`, `/ctf-forensics`, etc.)
- Agent has filesystem access to read challenge files

## Workflow

### Step 1: Initial Recon

Explore the challenge directory:
```
ls -la challenges/<challenge_name>/
file challenges/<challenge_name>/*
```

Identify all file types: text, binary, PCAP, image, Java, ELF, etc.

### Step 2: Categorize the Challenge

Use file extensions, content analysis, and description keywords to determine the category:

| Extension / Type       | Likely Category |
|------------------------|-----------------|
| .txt, .json, .html     | web / misc      |
| .pcap, .pcapng         | forensics       |
| .elf, .bin, .exe       | reverse / pwn   |
| .java, .class          | reverse         |
| .jpg, .png, .bmp       | forensics       |
| .enc, .key, .pem       | crypto          |
| .py                    | misc / reverse  |

### Step 3: Invoke Category Skill

Based on categorization, invoke the appropriate skill via `/ctf-<category>`.

### Step 4: Iterate and Pivot

If stuck after applying the category skill:
- Return to recon for missed details
- Try a different category if misidentified
- Look for hidden files, embedded data, or steganography

### Step 5: Capture the Flag

Flag format is typically `flag{...}`, `CTF{...}`, or similar. Search for the pattern:
```
grep -r "flag{" challenges/<challenge_name>/
```

## Verification

- Flag format matches expected pattern
- All challenge files have been examined
- Solution script is reproducible

## Common Patterns

- Hidden messages in plain sight (comments, whitespace, metadata)
- PCAP files contain exfiltrated data or credentials
- Binaries have hardcoded strings or embedded secrets
- Images hide data in LSB, EXIF, or appended bytes
- Java code often has obfuscated flag fragments
