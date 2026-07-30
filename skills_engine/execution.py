from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel
from pydantic import Field

from agents.registry import AgentRegistry
from core.protocol import AgentMessage
from skills_engine.planner import PlanStep, TaskPlan

logger = logging.getLogger("skills_engine.execution")


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepResult(BaseModel):
    step_index: int
    agent_name: str
    task: str
    status: ExecutionStatus
    response: str = ""
    error: Optional[str] = None
    attempts: int = 1


class ExecutionResult(BaseModel):
    plan_analysis: str
    step_results: list[StepResult]
    overall_status: ExecutionStatus
    error_summary: Optional[str] = None
    skills_used: list[dict] = []

    def to_legacy_dicts(self) -> list[dict]:
        return [
            {
                "step": r.step_index,
                "agent": r.agent_name,
                "task": r.task,
                "status": "completed" if r.status == ExecutionStatus.COMPLETED else "failed",
                "response": r.response or (r.error or ""),
                "error": r.error,
            }
            for r in self.step_results
        ]

    def all_completed(self) -> bool:
        return all(r.status == ExecutionStatus.COMPLETED for r in self.step_results)


class ExecutionAgent:
    def __init__(
        self,
        registry: AgentRegistry,
        skill_selector=None,
        skill_injector=None,
        max_retries: int = 2,
    ):
        self.registry = registry
        self.skill_selector = skill_selector
        self.skill_injector = skill_injector
        self.max_retries = max_retries

    async def execute(
        self,
        plan: TaskPlan,
        request: str = "",
    ) -> ExecutionResult:
        steps = plan.steps
        step_results: list[StepResult] = []
        completed: set[int] = set()
        step_outputs: dict[int, str] = {}
        all_skills: list[dict] = []

        while len(completed) < len(steps):
            dispatched = False
            for i, step in enumerate(steps):
                if i in completed:
                    continue
                deps = step.depends_on
                if not all(d in completed for d in deps):
                    continue
                result, step_skills = await self._execute_step(i, step, request)
                step_results.append(result)
                all_skills.extend(step_skills)
                if result.status == ExecutionStatus.COMPLETED:
                    step_outputs[i] = result.response
                    completed.add(i)
                    dispatched = True
                elif result.status == ExecutionStatus.FAILED:
                    completed.add(i)
                    dispatched = True
            if not dispatched:
                remaining = [s for i, s in enumerate(steps) if i not in completed]
                names = [s.agent for s in remaining]
                logger.error("Plan deadlocked — remaining steps: %s", names)
                for i, s in enumerate(steps):
                    if i not in completed:
                        step_results.append(
                            StepResult(
                                step_index=i,
                                agent_name=s.agent,
                                task=s.task,
                                status=ExecutionStatus.SKIPPED,
                                error="Deadlocked — unsatisfied dependencies",
                            )
                        )
                        completed.add(i)
                break

        failed = [r for r in step_results if r.status == ExecutionStatus.FAILED]
        skipped = [r for r in step_results if r.status == ExecutionStatus.SKIPPED]
        if failed or skipped:
            overall = ExecutionStatus.FAILED
            parts = []
            if failed:
                parts.append(f"{len(failed)} step(s) failed")
            if skipped:
                parts.append(f"{len(skipped)} step(s) skipped")
            error_summary = "; ".join(parts)
        else:
            overall = ExecutionStatus.COMPLETED
            error_summary = None

        seen_names = set()
        unique_skills = []
        for sk in all_skills:
            name = sk.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                unique_skills.append(sk)

        return ExecutionResult(
            plan_analysis=plan.analysis,
            step_results=step_results,
            overall_status=overall,
            error_summary=error_summary,
            skills_used=unique_skills,
        )

    async def _execute_step(
        self,
        index: int,
        step: PlanStep,
        request: str,
    ) -> tuple[StepResult, list[dict]]:
        agent = self.registry.get(step.agent)
        if not agent:
            err = f"Agent '{step.agent}' not found in registry."
            logger.warning("%s", err)
            return (
                StepResult(
                    step_index=index,
                    agent_name=step.agent,
                    task=step.task,
                    status=ExecutionStatus.FAILED,
                    response=err,
                    error=err,
                ),
                [],
            )

        step_skills: list[dict] = []
        if self.skill_selector and hasattr(agent, "set_skills"):
            skills = await self.skill_selector.select(
                task_context=step.task,
                agent_name=step.agent,
                limit=3,
            )
            agent.set_skills(skills)
            if skills:
                logger.info(
                    "Injected %d skill(s) into %s", len(skills), step.agent
                )
                step_skills = skills

        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "Executing step %d on %s (attempt %d/%d): %.60s",
                    index, step.agent, attempt, self.max_retries, step.task,
                )
                message = AgentMessage(
                    sender="supervisor",
                    receiver=step.agent,
                    task=step.task,
                    conversation_id=request[:40],
                )
                reply = await agent.receive(message)

                if reply.status == "completed":
                    return (
                        StepResult(
                            step_index=index,
                            agent_name=step.agent,
                            task=step.task,
                            status=ExecutionStatus.COMPLETED,
                            response=reply.response,
                            attempts=attempt,
                        ),
                        step_skills,
                    )
                else:
                    last_error = f"Agent returned status '{reply.status}': {reply.response[:200]}"
                    if attempt < self.max_retries:
                        logger.warning(
                            "Step %d failed (attempt %d/%d): %s",
                            index, attempt, self.max_retries, last_error,
                        )
                        await asyncio.sleep(attempt)
                        continue
                    return (
                        StepResult(
                            step_index=index,
                            agent_name=step.agent,
                            task=step.task,
                            status=ExecutionStatus.FAILED,
                            response=reply.response,
                            error=last_error,
                            attempts=attempt,
                        ),
                        step_skills,
                    )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Step %d exception (attempt %d/%d): %s",
                    index, attempt, self.max_retries, last_error,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(attempt)

        return (
            StepResult(
                step_index=index,
                agent_name=step.agent,
                task=step.task,
                status=ExecutionStatus.FAILED,
                error=last_error,
                attempts=self.max_retries,
            ),
            step_skills,
        )
