# 🤖 Agentic AI Security Harness

A Multi-Agent AI Framework for SOC Automation, Threat Analysis, and Cybersecurity Operations.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Docker](https://img.shields.io/badge/Docker-Supported-blue)
![Cybersecurity](https://img.shields.io/badge/Focus-Cybersecurity-red)
![AI](https://img.shields.io/badge/AI-Agentic%20AI-purple)

## Why This Project Exists

The Agentic AI Security Harness is developed as a learning and research project to explore how to design and build an Agentic AI system for cybersecurity applications, including potential use cases in Capture the Flag (CTF) competitions and security automation exercises.

## Target Users

This project is primarily designed for:

- Cybersecurity students
- Beginners interested in Artificial Intelligence (AI) and cybersecurity
- Aspiring security analysts who want to understand how AI agents can support security operations

The project provides a practical learning platform for exploring multi-agent architecture, security workflows, and AI-assisted cybersecurity analysis.

## Defensive Security Purpose

The Agentic AI Security Harness provides basic Tier-1 Security Operations Center (SOC) analysis capabilities to support initial security triage activities, including preliminary investigation, information gathering, and workflow automation.

This project is currently in an early development stage and requires further enhancement, testing, and validation before it can be considered suitable for real-world SOC operational environments.

## Architecture

The Agentic AI Security Harness follows a multi-agent architecture designed for SOC automation and cybersecurity analysis.

High-level workflow:
```
User Input → Orchestrator → Planner → Executor(s) → Reviewer → Response
```

Detailed workflow:

![Agentic AI Security Architecture](docs/agentic-ai-security-architecture.png)


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
