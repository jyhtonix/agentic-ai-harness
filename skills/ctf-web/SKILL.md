---
name: ctf-web
description: >-
  Web exploitation techniques for CTF challenges. Covers SQL injection,
  XSS, SSRF, path traversal, JWT attacks, authentication bypass, and
  common web vulnerability patterns seen in CTF competitions.
domain: ctf
subdomain: web
category: web
tags: [web, exploitation, http, sqli, xss, jwt, ssti, lfi]
version: "1.0"
author: "agent-harness"
allowed-tools: [Bash, Read, Write, Grep, WebFetch, WebSearch, Task]
requires: []
user_invocable: false
token_budget:
  frontmatter: 150
  full_content: 1200
---

## When to Use

When a challenge involves web technologies: HTTP responses, HTML/JS files, API endpoints, databases, or authentication mechanisms.

## Prerequisites

- Read access to challenge files
- WebFetch tool for HTTP requests
- Grep tool for searching source code

## Common Challenge Patterns

### Information Disclosure

Check for:
- Comments in HTML/JS source
- `/robots.txt`, `/sitemap.xml`, `/.git/`
- Debug endpoints, stack traces
- Exposed environment variables
- Directory listing enabled

### Authentication Bypass

Look for:
- Weak JWT secrets (try `john` rockyou or simple strings)
- JWT `alg: none` attack
- SQL injection in login forms: `' OR 1=1 --`
- NoSQL injection for MongoDB backends
- Insecure direct object references (IDOR)

### Server-Side Vulnerabilities

- SSTI in template engines: `{{7*7}}` → `49`
- LFI/RFI via path parameters: `?file=../../etc/passwd`
- SSRF to internal services
- Command injection in shell utilities

## Verification

- Request returns expected data
- Flag is present in response body or headers
- Authentication is successfully bypassed
