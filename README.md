

# 🤖 Agentic AI Security Harness

A Multi-Agent AI Framework for Cybersecurity Learning, SOC Automation Research, and CTF Security Analysis.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Docker](https://img.shields.io/badge/Docker-Supported-blue)
![Cybersecurity](https://img.shields.io/badge/Focus-Cybersecurity-red)
![AI](https://img.shields.io/badge/AI-Agentic%20AI-purple)
![License](https://img.shields.io/badge/License-MIT-green)

---

# Overview

The **Agentic AI Security Harness** is an educational and research-oriented **multi-agent AI cybersecurity framework** designed to explore how Agentic AI systems can assist cybersecurity analysis, security operations workflows, and Capture The Flag (CTF) problem-solving.

The project focuses on designing autonomous AI workflows where specialized agents collaborate to perform cybersecurity-related tasks:

* Security investigation
* Threat analysis
* Evidence collection
* CTF challenge analysis
* Reverse engineering assistance
* Malware analysis support
* Web security assessment
* Cybersecurity learning activities

The goal is to provide students, researchers, and cybersecurity practitioners with a practical platform to understand how AI agents can support security workflows.

---

# Project Motivation

Modern cybersecurity operations require analysts to perform many repetitive and time-consuming activities:

* Collecting investigation evidence
* Analysing suspicious files
* Reviewing logs
* Performing initial triage
* Documenting findings
* Creating investigation reports

This project explores how **Agentic AI workflows** can support cybersecurity analysts by combining:

* Planning agents
* Execution agents
* Specialist security agents
* Verification agents
* Learning and improvement mechanisms

The framework follows the concept of:

> Plan → Execute → Analyse → Verify → Improve

---

# Key Features

## Multi-Agent Cybersecurity Architecture

The framework includes specialised AI agents working together:

* Planner Agent

  * Breaks down security tasks
  * Creates investigation strategies

* Executor Agent

  * Executes approved tools and workflows

* Specialist Security Agents

  * Web Security Agent
  * Binary Reverse Engineering Agent
  * Malware Analysis Agent
  * Digital Forensics Agent
  * Cryptography Agent
  * Pwn Analysis Agent
  * DevOps Security Agent

* Reviewer / Verifier Agent

  * Validates findings
  * Improves investigation accuracy

---

## Agent Skill Registry System

The framework includes an extensible skill-based architecture.

Features:

* Dynamic skill discovery
* Specialist agent routing
* Security knowledge injection
* Skill validation
* Skill-based workflow planning

Example skill domains:

* Web exploitation
* Reverse engineering
* Malware analysis
* Digital forensics
* Cryptography
* CTF challenge solving

---

## Autonomous Learning and Improvement

The framework includes experimental learning capabilities:

* Agent performance tracking
* Investigation history
* Strategy evaluation
* Benchmark comparison
* Improvement feedback

The objective is to explore how AI security agents can gradually improve their problem-solving workflows.

---

## AI-Assisted CTF Security Analysis

The framework supports cybersecurity learning through CTF challenges.

Supported activities:

* Challenge understanding
* Evidence analysis
* Tool selection
* Investigation workflow planning
* Solution documentation

Example categories:

* Information disclosure
* Web security
* Binary reverse engineering
* Malware investigation
* Network analysis
* Cryptography

---

# Target Users

This project is designed for:

* Cybersecurity students
* Artificial Intelligence students
* Security researchers
* Beginner SOC analysts
* CTF participants
* Educators exploring AI-assisted cybersecurity learning

The project provides practical experience in:

* Multi-agent AI architecture
* Security automation
* AI-assisted investigation
* CTF solving methodology
* Cybersecurity workflow design

---

# Defensive Security Purpose

The Agentic AI Security Harness is designed for:

✅ Cybersecurity education
✅ Academic research
✅ CTF competitions
✅ Authorized security testing environments

The framework explores how AI agents can assist with:

* Security triage
* Evidence gathering
* Investigation assistance
* Workflow automation
* Report generation

This project is currently a research and educational framework.

Additional validation, testing, and security controls are required before considering operational SOC deployment.

---

# Architecture

The framework follows a multi-agent planning and execution architecture.

High-level workflow:

```
                 User Request
                      |
                      v
              Orchestrator Engine
                      |
                      v
               Planner Agent
                      |
        +-------------+-------------+
        |             |             |
        v             v             v

   Web Agent     Malware Agent   Binary Agent
   Crypto Agent  Forensics Agent Pwn Agent

        |
        v

        Security Tools Layer

        |
        v

     Verification Agent

        |
        v

     Final Investigation Report
```

---

## Security Architecture

Current architecture:

![Agentic AI Security Architecture](docs/agentic-ai-security-architecture.png)

Updated as of 2026-07-31:

![Agentic AI Security Architecture](docs/Security_Architecture_as_of_2026-07-31.png)



---

# System Structure

The project is organised into multiple layers:

```
agentic-ai-harness/

├── agents/                  # AI security agent implementations
├── api/                     # FastAPI application interface
├── core/                    # Agent orchestration and runtime engine
├── models/                  # LLM and embedding interfaces
├── tools/                   # Security analysis tools and execution framework
├── skills/                  # Agent skill definitions and routing
├── skill_packs/             # Cybersecurity domain knowledge packages
├── challenges/              # CTF challenges and security exercises
├── solutions/               # Investigation scripts and analysis artifacts
├── benchmark_engine/        # Agent evaluation and benchmarking
├── learning_engine/         # Autonomous learning components
├── database/                # Data storage and persistence layer
├── workflows/               # Security investigation workflows
├── tests/                   # Automated testing framework
├── docs/                    # Technical documentation
├── config/                  # Configuration management
├── prompts/                 # Specialist AI prompts
├── requirements.txt         # Python dependencies
└── README.md
```

---

# Component Overview

| Component           | Purpose                           |
| ------------------- | --------------------------------- |
| `agents/`           | AI cybersecurity agents           |
| `core/`             | Agent lifecycle and orchestration |
| `tools/`            | Security tool execution framework |
| `models/`           | LLM and embedding integration     |
| `skills/`           | Skill registry and routing system |
| `skill_packs/`      | Cybersecurity knowledge modules   |
| `challenges/`       | CTF learning scenarios            |
| `solutions/`        | Investigation outputs             |
| `benchmark_engine/` | Evaluation and comparison         |
| `learning_engine/`  | Improvement and feedback system   |
| `workflows/`        | Security workflow automation      |
| `tests/`            | Framework validation              |

---

# CTF Challenge Workflow

Example workflow:

```
CTF Challenge Input

        |
        v

AI Planning Agent

        |
        v

Security Investigation

        |
        v

Evidence Collection

        |
        v

Technical Analysis

        |
        v

Verification

        |
        v

Solution Report Generation
```

---

# Challenge Examples

Current challenge categories include:

```
challenges/

├── challenge01_hidden_message
├── challenge02_pcap_analysis
├── challenge03_binary_reverse
├── challenge04_StegoRSA
├── challenge05_reverse_eng
├── challenge06_binary_formatstring3
├── challenge07_binary_solfire
├── challenge08_web_SecretBox
├── challenge09_web_paper2
└── challenge12_web_liveArt
```

---

# Documentation

## Student Setup Guide

New users and students should read:

📘 [Student Setup Guide](STUDENT_SETUP_GUIDE.md)

The guide covers:

* Installing Python
* Creating virtual environment
* Installing dependencies
* Configuring environment variables
* Running the framework

---

## Technical Documentation

Available documentation:

* [Agent Skill Registry Architecture](docs/AGENT_SKILL_REGISTRY.md)
* [Autonomous Improvement Guide](docs/AUTONOMOUS_IMPROVEMENT_GUIDE.md)
* [CTF Benchmark Guide](docs/CTF_BENCHMARK_GUIDE.md)
* [Challenge Development Guide](docs/CHALLENGE_DEVELOPMENT_GUIDE.md)
* [Multi-Agent Guide](docs/MULTI_AGENT_GUIDE.md)

---

# Quick Start

## 1. Clone Repository

```bash
git clone https://github.com/jyhtonix/agentic-ai-harness.git

cd agentic-ai-harness
```

---

## 2. Create Virtual Environment

```bash
python -m venv .venv
```

Activate:

Windows:

```powershell
.venv\Scripts\activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment

Create:

```bash
.env
```

from:

```bash
.env.example
```

Configure required API keys.

---

## 5. Start Application

Recommended:

```powershell
python -m api.main
```

Alternative:

```bash
uvicorn api.main:app --reload
```

---

# Development Status

Current development areas:

✅ Multi-agent cybersecurity framework
✅ Agent skill registry
✅ AI-assisted CTF analysis
✅ Security investigation workflow
✅ Benchmark evaluation framework
✅ Autonomous improvement research
✅ Student cybersecurity learning platform

Future improvements:

* Additional specialist agents
* More CTF scenarios
* Improved tool integration
* Enhanced reporting
* More autonomous reasoning capabilities

---

# Responsible Use

This project is intended for:

* Cybersecurity education
* Research
* CTF competitions
* Authorized security testing

Users must only analyse systems, files, and networks where they have proper authorization.

This project must not be used for:

* Unauthorized access
* Malicious activities
* Attacking systems without permission

---

# License

This project is licensed under the MIT License.

Copyright (c) 2026 Soo Weng Jyh

---

# Citation

If you use this project for research, education, academic work, or publications, please cite:

Soo Weng Jyh (2026).

**"Agentic AI Security Harness: An Autonomous Multi-Agent Cybersecurity Framework."**

GitHub repository:

https://github.com/jyhtonix/agentic-ai-harness

---

# Acknowledgement

If this project contributes to your research, education activities, or cybersecurity competitions, acknowledgement of this project and its creator is appreciated.
