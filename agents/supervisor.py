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

logger = logging.getLogger("agent.supervisor")

SUPERVISOR_SYSTEM_PROMPT = """You are a Supervisor Agent. You coordinate
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
    """

    def __init__(self, llm: LLM, registry: AgentRegistry):
        self.llm = llm
        self.registry = registry
        self.conversation_history: list[AgentMessage] = []

    async def run(self, request: str) -> dict:
        """
        Execute the full supervisor workflow for a user request.
        Returns a dict with the dispatch plan, individual agent results,
        and the final synthesised response.
        """
        logger.info("Supervisor processing request: %.60s", request)

        # Phase 1: Analyse and plan
        plan = await self._create_dispatch_plan(request)
        logger.info("Dispatch plan: %d steps", len(plan.get("steps", [])))

        # Phase 2: Execute the plan
        results = await self._execute_plan(request, plan)

        # Phase 3: Synthesize final response
        final = await self._synthesize(request, results)

        return {
            "request": request,
            "analysis": plan.get("analysis", ""),
            "plan": plan.get("steps", []),
            "agent_results": results,
            "final_response": final,
        }

    async def _create_dispatch_plan(self, request: str) -> dict:
        """
        Phase 1: Analyse the request and determine which agents to dispatch.
        """
        agents_desc = json.dumps(self.registry.list_agents(), indent=2)
        prompt = SUPERVISOR_SYSTEM_PROMPT.format(agents=agents_desc)

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

    async def _synthesize(self, request: str, results: list[dict]) -> str:
        """
        Phase 3: Combine all agent results into a coherent final response.
        """
        results_text = json.dumps([
            {"agent": r["agent"], "status": r["status"], "response_preview": r["response"][:500]}
            for r in results
        ], indent=2)

        prompt = SYNTHESIS_PROMPT.format(request=request, results=results_text)
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
