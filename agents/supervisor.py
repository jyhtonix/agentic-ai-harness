"""
Supervisor Agent.

Purpose: Central coordinator in the multi-agent system. Receives user
requests, decomposes them into sub-tasks, assigns each to the appropriate
specialized agent, collects results, and produces a final integrated
response.

Workflow:
  1. Receive user request → analyse with LLM
  2. Determine required agents and build a dispatch plan
  3. Send tasks to each agent in dependency order
  4. Collect and integrate results
  5. Generate final response

Clean architecture: The Supervisor depends on the AgentRegistry to
discover agents, and on the LLM for analysis and synthesis. It does
not import any specialized agent directly.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from models.llm import LLM, LLMResponse
from core.protocol import AgentMessage
from agents.registry import AgentRegistry
from skills_engine.planner import PlanStep, TaskPlan

logger = logging.getLogger("agent.supervisor")

VERIFICATION_PROMPT_SECTION = """

Verification Results:
{verification}

Note: The verification above provides confidence scoring and may identify
issues. Address any flagged concerns in your response, especially if the
confidence score is low."""

LEARNING_REPORT_PROMPT_SECTION = """

Learning Report:
{learning_report}

The learning report above provides educational context. Incorporate
relevant learning objectives and recommendations into your final
response, especially improvement suggestions for the student."""

# Legacy prompt — used only when no SkillPlanner is provided.
# When a SkillPlanner is wired, it owns its own DISPATCH_SYSTEM_PROMPT.
LEGACY_DISPATCH_PROMPT = """You are a Supervisor Agent. You coordinate
specialized agents to complete complex user requests.

For each request:
1. Analyse what the user needs
2. Identify which specialized agents are required
3. Plan the order of operations (parallel vs sequential)
4. After receiving all results, synthesise a final response

Available agents: {agents}

Return a JSON plan with:
- analysis: your understanding of the request
- steps: array of objects with keys: agent, task, depends_on
- depends_on: list of step indices that must complete first"""

SYNTHESIS_PROMPT = """You are a Supervisor Agent. Synthesize the following
results from multiple specialized agents into a coherent final response
for the user.

Original request: {request}

Agent results:
{results}

Produce a comprehensive, well-structured final answer that integrates
all findings."""


class SupervisorAgent:
    """
    Central coordinator that dispatches work to specialized agents
    and synthesises their results into a final response.

    Skill integration: When a skill_selector is provided, the supervisor
    selects relevant CTF skills for each agent before dispatching, so
    agents receive contextual expertise without changing their code.

    Planning delegation: When a planner (SkillPlanner) is provided,
    dispatch planning is delegated to it. Otherwise the supervisor
    falls back to its internal LLM-based planning for backward
    compatibility.

    Execution delegation: When an execution_agent (ExecutionAgent) is
    provided, plan execution is delegated to it instead of running
    the inline _execute_plan loop.

    Verification: When a verifier (VerificationAgent) is provided,
    agent results are reviewed before synthesis for evidence quality,
    flag format correctness, and hallucination detection.

    Learning report: When a report_generator (LearningReportGenerator)
    is provided, an educational feedback report is generated after
    verification and included in the synthesis context.

    Challenge orchestration: When a challenge_loader and flag_verifier are
    provided, the supervisor can pre-load a challenge by ID, validate it,
    inject challenge context into the pipeline, and run flag verification
    on results.
    """

    def __init__(self, llm: LLM, registry: AgentRegistry,
                 skill_selector=None, planner=None,
                 execution_agent=None, verifier=None,
                 report_generator=None,
                 challenge_loader=None,
                 flag_verifier=None,
                 coordinator=None,
                 memory_service=None):
        self.llm = llm
        self.registry = registry
        self.skill_selector = skill_selector
        self.planner = planner
        self.execution_agent = execution_agent
        self.verifier = verifier
        self.report_generator = report_generator
        self.challenge_loader = challenge_loader
        self.flag_verifier = flag_verifier
        self.coordinator = coordinator
        self.memory_service = memory_service
        self.conversation_history: list[AgentMessage] = []

    async def run(self, request: str, challenge_id: str = "") -> dict:
        """
        Execute the full supervisor workflow for a user request.
        Returns a dict with the dispatch plan, individual agent results,
        and the final synthesised response.
        """
        logger.info("Supervisor processing request: %.60s", request)

        # Phase 0: Load challenge if challenge_loader is wired
        challenge_def = None
        flag_result = None
        if self.challenge_loader and challenge_id:
            challenge_def = self.challenge_loader.load(challenge_id)
            if challenge_def:
                logger.info("Loaded challenge: %s (%s)", challenge_def.name, challenge_def.category)
                request = f"[Challenge: {challenge_def.name}]\n{challenge_def.description}\n\n{request}"

        # Phase 1: Analyse and plan
        plan = await self._create_dispatch_plan(request, category=challenge_def.category if challenge_def else "")
        logger.info("Dispatch plan: %d steps", len(plan.get("steps", [])))
        # Phase 2: Team coordination (if coordinator is available)
        team_coordination = None
        if self.coordinator:
            logger.info("Using coordinator agent for team-based execution")
            context = None
            if challenge_def:
                context = {"challenge_name": challenge_def.name, "category": challenge_def.category}
            team_coordination = await self.coordinator.coordinate(request, context)
            results = [{
                "step": 0,
                "agent": f["agent_name"],
                "task": f["category"],
                "status": "completed",
                "response": "; ".join(f["findings"]) if f["findings"] else "",
            } for f in team_coordination.get("findings", [])]
            if not results:
                results = [{
                    "step": 0,
                    "agent": "team_coordinator",
                    "task": request,
                    "status": "completed",
                    "response": team_coordination.get("consolidated", {}).get("summary", ""),
                }]
            logger.info("Team coordination produced %d findings", len(results))

        # Phase 2b: Execute the plan (skipped if coordinator was used)
        execution_result_ref = None
        if team_coordination is None:
            if self.execution_agent:
                task_plan = self._dict_to_task_plan(plan)
                execution_result_ref = await self.execution_agent.execute(task_plan, request=request)
                results = execution_result_ref.to_legacy_dicts()
                for r in execution_result_ref.step_results:
                    if r.response:
                        self.conversation_history.append(
                            AgentMessage(
                                sender="supervisor", receiver=r.agent_name,
                                task=r.task, conversation_id=request[:40],
                            )
                        )
                        self.conversation_history.append(
                            AgentMessage(
                                sender=r.agent_name, receiver="supervisor",
                                response=r.response, conversation_id=request[:40],
                            )
                        )
            else:
                results = await self._execute_plan(request, plan)

        # Phase 3: Verify results
        verification = None
        if self.verifier:
            plan_steps = plan.get("steps", [])
            verification = await self.verifier.verify(
                request=request,
                plan=plan_steps,
                agent_results=results,
            )
            logger.info(
                "Verification: status=%s confidence=%.2f issues=%d",
                verification.status.value,
                verification.confidence_score,
                len(verification.issues),
            )

        # Phase 4: Generate learning report
        learning_report = None
        if self.report_generator:
            skills_used = getattr(execution_result_ref, "skills_used", []) if execution_result_ref else []
            tools_used = _extract_tools_from_results(results)
            learning_report = self.report_generator.generate(
                request=request,
                skills_used=skills_used,
                verification_result=verification,
                agent_results=results,
                challenge_info={
                    "name": challenge_def.name,
                    "category": challenge_def.category,
                    "difficulty": challenge_def.difficulty,
                } if challenge_def else None,
                flag_result={
                    "status": flag_result.status,
                    "method": flag_result.method,
                    "detail": flag_result.detail,
                } if flag_result else None,
                tools_used=tools_used,
            )
            logger.info(
                "Learning report: challenge=%s difficulty=%s objectives=%d",
                learning_report.challenge_id,
                learning_report.difficulty_estimate,
                len(learning_report.learning_objectives),
            )

        # Phase 4.5: Flag verification (if challenge is loaded)
        flag_result = None
        if self.flag_verifier and challenge_def:
            tool_outputs = _collect_tool_outputs(results)
            flag_result = self.flag_verifier.verify(
                challenge=challenge_def,
                agent_response="\n".join(r.get("response", "") for r in results),
                tool_outputs=tool_outputs,
            )
            logger.info("Flag verification: %s (method=%s)", flag_result.status, flag_result.method)

        # Phase 5: Synthesize final response
        final = await self._synthesize(request, results, verification, learning_report)

        return {
            "request": request,
            "analysis": plan.get("analysis", ""),
            "plan": plan.get("steps", []),
            "agent_results": results,
            "verification": verification.model_dump() if verification else None,
            "learning_report": learning_report.model_dump() if learning_report else None,
            "flag_verification": {
                "status": flag_result.status,
                "method": flag_result.method,
                "detail": flag_result.detail,
                "student_flag": flag_result.student_flag,
            } if flag_result else None,
            "challenge": {
                "name": challenge_def.name,
                "category": challenge_def.category,
                "difficulty": challenge_def.difficulty,
            } if challenge_def else None,
            "team_coordination": team_coordination,
            "final_response": final,
        }

    async def _create_dispatch_plan(self, request: str, category: str = "") -> dict:
        """
        Phase 1: Analyse the request and determine which agents to dispatch.
        Delegates to SkillPlanner if available, otherwise uses the built-in
        LLM-based planning for backward compatibility.
        """
        if self.planner:
            plan = await self.planner.create_plan(request, category=category)
            return plan.to_dict()

        agents_desc = json.dumps(self.registry.list_agents(), indent=2)
        skills_desc = ""
        if self.skill_selector:
            categories = self.skill_selector.registry.get_categories() if hasattr(self.skill_selector, "registry") else {}
            if categories:
                skills_desc = "\nAvailable skill categories:\n" + "\n".join(
                    f"  - {cat}: {count} skill(s)" for cat, count in sorted(categories.items())
                )

        prompt = LEGACY_DISPATCH_PROMPT.format(agents=agents_desc) + skills_desc

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Analyse this request and create a dispatch plan:\n\n{request}"},
        ]

        response = await self.llm.chat(messages, temperature=0.3)

        try:
            plan = json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Supervisor plan was not valid JSON, using fallback")
            plan = self._fallback_plan(request)

        return plan

    async def _execute_plan(self, request: str, plan: dict) -> list[dict]:
        """
        Phase 2: Execute each step in the dispatch plan.
        Respects dependency ordering (steps with depends_on wait).
        """
        steps = plan.get("steps", [])
        results: list[dict] = []
        completed: set[int] = set()
        step_outputs: dict[int, str] = {}

        while len(completed) < len(steps):
            dispatched = False
            for i, step in enumerate(steps):
                if i in completed:
                    continue

                deps = step.get("depends_on", [])
                if not all(d in completed for d in deps):
                    continue

                agent_name = step.get("agent", "")
                task = step.get("task", "")
                agent = self.registry.get(agent_name)

                if not agent:
                    logger.warning("Agent '%s' not found in registry", agent_name)
                    step_outputs[i] = f"Error: Agent '{agent_name}' not available."
                    result_entry = {
                        "step": i,
                        "agent": agent_name,
                        "task": task,
                        "status": "failed",
                        "response": f"Agent '{agent_name}' not found.",
                    }
                else:
                    if self.skill_selector and hasattr(agent, "set_skills"):
                        skills = await self.skill_selector.select(
                            task_context=task,
                            agent_name=agent_name,
                            limit=3,
                        )
                        agent.set_skills(skills)
                        if skills:
                            logger.info("Injected %d skill(s) into %s", len(skills), agent_name)

                    logger.info("Dispatching to %s: %.60s", agent_name, task)
                    message = AgentMessage(
                        sender="supervisor",
                        receiver=agent_name,
                        task=task,
                        conversation_id=request[:40],
                    )
                    reply = await agent.receive(message)
                    step_outputs[i] = reply.response

                    result_entry = {
                        "step": i,
                        "agent": agent_name,
                        "task": task,
                        "status": reply.status,
                        "response": reply.response,
                    }
                    self.conversation_history.append(message)
                    self.conversation_history.append(reply)

                results.append(result_entry)
                completed.add(i)
                dispatched = True

            if not dispatched:
                logger.error("Plan deadlocked — no steps can be dispatched")
                break

        return results

    async def _synthesize(
        self,
        request: str,
        results: list[dict],
        verification=None,
        learning_report=None,
    ) -> str:
        """
        Phase 5: Combine all agent results into a coherent final response.
        Optionally includes verification and learning report for context.
        """
        results_text = json.dumps([
            {"agent": r["agent"], "status": r["status"], "response_preview": r["response"][:500]}
            for r in results
        ], indent=2)

        prompt = SYNTHESIS_PROMPT.format(request=request, results=results_text)

        if verification:
            v = verification.model_dump() if hasattr(verification, "model_dump") else verification
            prompt += VERIFICATION_PROMPT_SECTION.format(
                verification=json.dumps(v, indent=2),
            )

        if learning_report:
            lr = learning_report.model_dump() if hasattr(learning_report, "model_dump") else learning_report
            prompt += LEARNING_REPORT_PROMPT_SECTION.format(
                learning_report=json.dumps(lr, indent=2),
            )

        messages = [
            {"role": "system", "content": "You are a skilled report synthesizer."},
            {"role": "user", "content": prompt},
        ]

        response = await self.llm.chat(messages, temperature=0.4)
        return response.content

    def _fallback_plan(self, request: str) -> dict:
        """
        Fallback plan when the LLM plan is not valid JSON.
        Creates a generic single-step plan using all registered agents.
        """
        agents = list(self.registry.list_agents().keys())
        steps = [
            {"agent": agent, "task": request, "depends_on": []}
            for agent in agents
        ]
        return {
            "analysis": f"Analyse: {request}",
            "steps": steps,
        }

    @staticmethod
    def _dict_to_task_plan(plan: dict) -> TaskPlan:
        """Convert a legacy dict plan into a typed TaskPlan."""
        steps = [
            PlanStep(agent=s["agent"], task=s["task"], depends_on=s.get("depends_on", []))
            for s in plan.get("steps", [])
        ]
        return TaskPlan(
            analysis=plan.get("analysis", ""),
            steps=steps,
        )


def _collect_tool_outputs(results: list[dict]) -> list[dict]:
    """Extract tool execution outputs from agent results for flag verification."""
    tool_outputs = []
    for r in results:
        response = r.get("response", "")
        if "[Tool Execution Evidence]" in response:
            tool_outputs.append({"tool": "agent", "output": response})
    return tool_outputs


def _extract_tools_from_results(results: list[dict]) -> list[str]:
    """Extract tool names referenced in agent responses."""
    tools = set()
    for r in results:
        response = r.get("response", "")
        for tool_name in ["strings", "file", "exiftool", "yara", "capa", "binwalk", "curl", "python"]:
            if tool_name in response.lower():
                tools.add(tool_name)
    return sorted(tools)
