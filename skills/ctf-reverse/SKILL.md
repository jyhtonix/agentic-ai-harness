---
name: ctf-reverse
description: >-
  Reverse engineering techniques for CTF challenges. Covers ELF binary
  analysis, string extraction, disassembly, Java reverse engineering,
  and deobfuscation of compiled code.
domain: ctf
subdomain: reverse
category: reverse
tags: [reverse, binary, elf, disassembly, java, strings, ghidra]
version: "1.0"
author: "agent-harness"
allowed-tools: [Bash, Read, Write, Grep, Glob, Task]
requires: []
user_invocable: false
token_budget:
  frontmatter: 150
  full_content: 1500
---

## When to Use

When a challenge involves compiled programs: ELF binaries (challenges/challenge03_binary_reverse/), Java class files (challenges/challenge05_reverse_eng/), executables, or any compiled code requiring analysis.

## Prerequisites

- Read access to binary files
- `strings`, `file`, `xxd` or `hexdump` commands
- Python for writing analysis scripts

## Common Challenge Patterns

### ELF Binary Analysis (challenges/challenge03_binary_reverse/)

```
file authorize binary1
strings authorize | grep -i flag
strings binary1 | grep -i ctf
```

### Java Reverse Engineering (challenges/challenge05_reverse_eng/VaultDoorTraining.java)

For Java challenges:
- Read the source code directly (often provided)
- Look for character-by-character password checks
- The flag is usually constructed from individual characters tested in the check function

### General Binary Analysis

```python
# Read binary and extract printable strings
with open("binary", "rb") as f:
    data = f.read()
    strings = []
    current = []
    for byte in data:
        if 32 <= byte <= 126:
            current.append(chr(byte))
        else:
            if len(current) >= 4:
                strings.append("".join(current))
            current = []
    for s in strings:
        print(s)
```

## Verification

- Decompiled logic reveals password or flag
- Obfuscation successfully removed
- Original algorithm reconstructed
