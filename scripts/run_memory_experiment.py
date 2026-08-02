#!/usr/bin/env python3
"""
Run the memory A/B experiment against a live LLM.

Compares memory-disabled vs memory-enabled solving on the same challenges.

Usage:
    python scripts/run_memory_experiment.py
    python scripts/run_memory_experiment.py --challenges crypto_basic_001,web_basic_001
    python scripts/run_memory_experiment.py --memory-dir benchmark/memory_experiments/store \
        --output benchmark/memory_experiments/report.json
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("run_memory_experiment")

DEFAULT_CHALLENGES = [
    "crypto_basic_001",
    "web_basic_001",
    "malware_basic_001",
    "forensics_basic_001",
    "stego_basic_001",
]


def build_supervisor(memory_service):
    """Build the production supervisor stack, mirroring api/main.py wiring."""
    from models.llm import OpenAILLM
    from agents.registry import AgentRegistry
    from agents.supervisor import SupervisorAgent
    from agents.verifier import VerificationAgent
    from learning.report import LearningReportGenerator
    from agents.researcher import ResearchAgent
    from agents.coder import CodingAgent
    from agents.security import SecurityAgent
    from agents.qa import QAAgent
    from agents.alert_analyst import AlertAnalystAgent
    from agents.threat_hunter import ThreatHunterAgent
    from agents.malware_analyst import MalwareAnalystAgent
    from agents.incident_responder import IncidentResponderAgent
    from tools.web_search import search as web_search_tool
    from tools.code_runner import run as code_runner_tool

    from skills_engine.registry import SkillRegistry
    from skills_engine.selector import SkillSelector
    from skills_engine.injector import SkillInjector
    from skills_engine.planner import SkillPlanner
    from skills_engine.execution import ExecutionAgent

    from challenges_engine.loader import ChallengeLoader
    from challenges_engine.verifier import FlagVerifier

    llm = OpenAILLM()

    registry = AgentRegistry()
    registry.register(ResearchAgent(llm, web_search_tool=web_search_tool))
    registry.register(CodingAgent(llm, code_runner_tool=code_runner_tool))
    registry.register(SecurityAgent(llm))
    registry.register(QAAgent(llm))
    registry.register(AlertAnalystAgent(llm))
    registry.register(ThreatHunterAgent(llm))
    registry.register(MalwareAnalystAgent(llm))
    registry.register(IncidentResponderAgent(llm))

    skill_registry = SkillRegistry()
    skill_selector = SkillSelector(skill_registry)
    skill_injector = SkillInjector(budget=2048)
    skill_planner = SkillPlanner(
        llm=llm,
        registry=registry,
        skill_selector=skill_selector,
        memory_service=memory_service,
    )
    execution_agent = ExecutionAgent(
        registry=registry,
        skill_selector=skill_selector,
        skill_injector=skill_injector,
    )
    verifier = VerificationAgent()
    report_generator = LearningReportGenerator()

    supervisor = SupervisorAgent(
        llm,
        registry,
        skill_selector=skill_selector,
        planner=skill_planner,
        execution_agent=execution_agent,
        verifier=verifier,
        report_generator=report_generator,
        challenge_loader=ChallengeLoader(),
        flag_verifier=FlagVerifier(),
        memory_service=memory_service,
    )
    return supervisor


async def build_supervisor_async(memory_service):
    return build_supervisor(memory_service)


def main():
    parser = argparse.ArgumentParser(description="Run memory A/B experiment")
    parser.add_argument(
        "--challenges",
        default=",".join(DEFAULT_CHALLENGES),
        help="Comma-separated challenge ids (default: 5 basic challenges)",
    )
    parser.add_argument(
        "--memory-dir",
        default="benchmark/memory_experiments/store",
        help="Directory for the experiment MemoryService (default: benchmark/memory_experiments/store)",
    )
    parser.add_argument(
        "--output",
        default="benchmark/memory_experiments/report.json",
        help="Path for the JSON report (default: benchmark/memory_experiments/report.json)",
    )
    parser.add_argument(
        "--dataset-name",
        default="memory_ab_basic",
        help="Dataset name label in the report",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=None,
        help="Max attempts per challenge (default: retry controller default)",
    )
    args = parser.parse_args()

    challenge_ids = [c.strip() for c in args.challenges.split(",") if c.strip()]

    from benchmark_engine.memory_experiment import MemoryExperiment
    from challenges_engine.loader import ChallengeLoader

    loader = ChallengeLoader()
    missing = [c for c in challenge_ids if loader.load(c) is None]
    if missing:
        logger.error("Unknown challenges: %s", ", ".join(missing))
        sys.exit(1)

    experiment = MemoryExperiment(
        challenge_ids=challenge_ids,
        supervisor_builder=build_supervisor_async,
        loader=loader,
        memory_dir=args.memory_dir,
        max_attempts=args.max_attempts,
        dataset_name=args.dataset_name,
    )

    report = asyncio.run(experiment.run())

    print(report.summary_table())

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_json(), encoding="utf-8")
    logger.info("Report written to %s", output_path)

    print(report.to_json())


if __name__ == "__main__":
    main()
