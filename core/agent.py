"""
Agent Runtime Engine.

Purpose: Implements the full agent lifecycle — from receiving a user
request to producing a final response. Each phase is a separate method
so the lifecycle is transparent, testable, and extensible.

Lifecycle:
  USER REQUEST → initialize()
  → TASK ANALYSIS → understand_task()
  → PLANNING → create_plan()
  → TOOL SELECTION → execute_plan() [per-step]
  → EXECUTION → execute_plan() [per-step]
  → RESULT VALIDATION → evaluate_result()
  → REFLECTION → reflect()
  → FINAL RESPONSE → respond()

Clean architecture: The Agent depends on the LLM abstract interface
and a ToolRegistry abstraction. It does not import concrete tool
implementations directly.
"""

import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models.llm import LLM, LLMResponse, LLMUsage
from tools.base import BaseTool
from tools.registry import ToolRegistry as BaseToolRegistry
from core.cache import llm_cache
from core.monitoring import metrics, METRIC_LLM_CALLS, METRIC_LLM_TOKENS

logger = logging.getLogger("agent.runtime")


# ---------------------------------------------------------------------------
# Base agent (legacy interface for specialized agents)
# ---------------------------------------------------------------------------

@dataclass
class AgentContext:
    """Context passed to specialized agents when they execute."""
    task_id: str
    objective: str
    plan: Optional[dict] = None
    previous_results: list[str] = field(default_factory=list)


@dataclass
class AgentResult:
    """Standardised result returned by a specialized agent."""
    agent_name: str
    success: bool
    output: str
    error: Optional[str] = None


class BaseAgent(ABC):
    """Abstract base for specialized agents (Planner, Executor, etc.)."""

    def __init__(self, name: str, llm: LLM, system_prompt: str):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        ...


# ---------------------------------------------------------------------------
# Token tracking
# ---------------------------------------------------------------------------

@dataclass
class TokenTracker:
    """Accumulates token usage across all LLM calls in a session."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, usage: LLMUsage) -> None:
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.total_tokens += usage.total_tokens

    def summary(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    """Complete runtime state of the agent across its lifecycle."""
    task: str = ""                      # Original user request
    goal: str = ""                      # Parsed objective
    messages: list[dict] = field(default_factory=list)  # LLM conversation
    plan: list[dict] = field(default_factory=list)      # Structured plan steps
    tools_used: list[str] = field(default_factory=list)  # Tools invoked
    results: list[dict] = field(default_factory=list)   # Step-by-step results
    errors: list[str] = field(default_factory=list)     # Accumulated errors
    final_answer: str = ""              # Final response to user
    start_time: float = 0.0             # Lifecycle timestamp
    tokens: TokenTracker = field(default_factory=TokenTracker)


# ---------------------------------------------------------------------------
# Lifecycle prompts
# ---------------------------------------------------------------------------

TASK_ANALYSIS_PROMPT = """You are a task analysis system. Analyse the following
user request and extract the core objective and success criteria.

User request: {task}

Return a JSON object with these keys:
- goal: a concise statement of the objective
- success_criteria: how we will know the task is complete
- complexity: "simple" | "moderate" | "complex"
- required_capabilities: list of skills or resources needed"""

PLANNING_PROMPT = """You are a planning system. Break the following goal into
concrete, actionable steps.

Goal: {goal}
Available tools: {tools}

For each step specify:
- step: step number
- action: what to do
- tool: which tool to use (or "none" if reasoning only)
- expected_outcome: what success looks like

Return a JSON object with a "steps" array."""

REFLECTION_PROMPT = """You are a reflection engine. Analyse the task execution
and identify what worked, what didn't, and what could be improved.

Goal: {goal}
Results: {results}
Errors: {errors}

Return a JSON object with keys:
- summary: one-line assessment
- lessons_learned: list of insights
- improvement_suggestions: list of specific improvements"""


# ---------------------------------------------------------------------------
# Exception wrapper
# ---------------------------------------------------------------------------

class AgentError(Exception):
    """Base exception for agent lifecycle failures."""
    pass


class TaskAnalysisError(AgentError):
    """Raised when task understanding fails."""
    pass


class PlanningError(AgentError):
    """Raised when plan creation fails."""
    pass


class ExecutionError(AgentError):
    """Raised when a step execution fails after all retries."""
    pass


# ---------------------------------------------------------------------------
# Agent runtime
# ---------------------------------------------------------------------------

TOOL_SELECTION_PROMPT = """You are a tool selection system. Based on the task
and the available tools, choose the best tool and provide the parameters.

Task: {task}
Available tools: {tools}

Return a JSON object with:
- tool: the name of the tool to use (or "none" if no tool is needed)
- reason: why this tool was chosen
- parameters: object with the parameters to pass to the tool"""


class Agent:
    """
    Full lifecycle agent runtime with automatic tool selection.

    Usage:
        agent = Agent(llm=OpenAILLM())
        agent.tools.register(WebSearchTool())
        result = await agent.run("Write a poem about Python")
    """

    def __init__(self, llm: LLM, memory_manager=None):
        self.llm = llm
        self.tools = BaseToolRegistry()
        self.state = AgentState()
        self.memory = memory_manager

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, task: str) -> dict:
        """
        Execute the full agent lifecycle for a user request.
        Returns a summary dict with the final answer and metadata.
        """
        self.initialize(task)
        logger.info("Agent lifecycle started | task=%.60s", task)

        if self.memory:
            await self.memory.on_new_task(task=task)

        try:
            await self.understand_task()
            await self.create_plan()
            await self.execute_plan()
            await self.evaluate_result()
            await self.reflect()
            await self.respond()
        except AgentError:
            logger.exception("Agent lifecycle failed at state=%s", self.state.goal)
            self.state.final_answer = (
                f"I encountered an error while processing your request.\n"
                f"Errors: {'; '.join(self.state.errors[-3:])}"
            )
        except Exception as e:
            logger.exception("Unhandled agent error")
            self.state.errors.append(f"Unhandled: {e}")
            self.state.final_answer = "An unexpected error occurred. Please try again."

        if self.memory and self.state.final_answer:
            await self.memory.on_task_complete(
                task=task,
                result=self.state.final_answer,
                success=len(self.state.errors) == 0,
                metadata={"token_usage": self.state.tokens.summary()},
            )

        elapsed = time.time() - self.state.start_time
        logger.info(
            "Agent lifecycle complete | elapsed=%.2fs tokens=%d errors=%d",
            elapsed,
            self.state.tokens.total_tokens,
            len(self.state.errors),
        )

        return self._summary(elapsed)

    # ------------------------------------------------------------------
    # Lifecycle phases
    # ------------------------------------------------------------------

    def initialize(self, task: str) -> None:
        """
        Phase 0: Initialise agent state.
        Resets all fields and stores the raw user request.
        """
        self.state = AgentState(
            task=task,
            start_time=time.time(),
        )
        self.state.messages.append({"role": "user", "content": task})
        logger.debug("State initialised with task='%.60s'", task)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(TaskAnalysisError),
    )
    async def understand_task(self) -> None:
        """
        Phase 1: Task analysis.
        Send the raw request to the LLM and extract a structured goal.
        """
        logger.debug("Phase 1: understand_task")

        prompt = TASK_ANALYSIS_PROMPT.format(task=self.state.task)
        messages = [
            {"role": "system", "content": "You are a precise task analyser."},
            {"role": "user", "content": prompt},
        ]

        response = await self._safe_chat(messages, temperature=0.3)
        self.state.tokens.add(response.usage)

        try:
            analysis = json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as e:
            self.state.errors.append(f"Task analysis parse failed: {e}")
            raise TaskAnalysisError(f"Failed to parse analysis: {e}") from e

        self.state.goal = analysis.get("goal", self.state.task)
        self.state.messages.append({
            "role": "assistant",
            "content": f"Goal identified: {self.state.goal}",
        })
        logger.info("Goal identified: %s", self.state.goal)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(PlanningError),
    )
    async def create_plan(self) -> None:
        """
        Phase 2: Planning.
        Decompose the goal into a sequence of concrete steps.
        """
        logger.debug("Phase 2: create_plan")

        tools_desc = json.dumps(self.tools.list_tools(), indent=2)
        prompt = PLANNING_PROMPT.format(goal=self.state.goal, tools=tools_desc)
        messages = [
            {"role": "system", "content": "You are a precise planner."},
            {"role": "user", "content": prompt},
        ]

        response = await self._safe_chat(messages, temperature=0.3)
        self.state.tokens.add(response.usage)

        try:
            plan_data = json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as e:
            self.state.errors.append(f"Plan parse failed: {e}")
            raise PlanningError(f"Failed to parse plan: {e}") from e

        self.state.plan = plan_data.get("steps", [])
        self.state.messages.append({
            "role": "assistant",
            "content": f"Plan created with {len(self.state.plan)} steps.",
        })
        logger.info("Plan created with %d steps", len(self.state.plan))

    async def execute_plan(self) -> None:
        """
        Phase 3-4: Tool selection and execution.
        Iterates plan steps, auto-selects tools when the plan specifies
        a tool name or when a step clearly requires a tool.
        """
        logger.debug("Phase 3-4: execute_plan (%d steps)", len(self.state.plan))

        for step in self.state.plan:
            step_num = step.get("step", "?")
            action = step.get("action", "")
            tool_name = step.get("tool", "none")
            logger.info("Executing step %s: %.80s", step_num, action)

            step_result = {
                "step": step_num,
                "action": action,
                "tool": tool_name,
                "success": False,
                "output": "",
                "error": None,
            }

            try:
                if tool_name and tool_name != "none" and self.tools.get_tool(tool_name):
                    output = await self._invoke_tool(tool_name, action)
                    step_result["output"] = output
                    step_result["tool"] = tool_name
                    step_result["success"] = True

                elif self.tools.list_tools():
                    selected = await self._auto_select_tool(action)
                    chosen_tool = selected.get("tool", "none")
                    if chosen_tool and chosen_tool != "none":
                        params = selected.get("parameters", {})
                        output = await self._invoke_tool(chosen_tool, action, params)
                        step_result["output"] = output
                        step_result["tool"] = chosen_tool
                        step_result["success"] = True
                    else:
                        response = await self._reasoning_step(action)
                        self.state.tokens.add(response.usage)
                        step_result["output"] = response.content
                        step_result["success"] = True
                else:
                    response = await self._reasoning_step(action)
                    self.state.tokens.add(response.usage)
                    step_result["output"] = response.content
                    step_result["success"] = True

            except Exception as e:
                logger.warning("Step %s failed: %s", step_num, e)
                step_result["error"] = str(e)
                self.state.errors.append(f"Step {step_num}: {e}")

            self.state.results.append(step_result)

    async def _auto_select_tool(self, action: str) -> dict:
        """
        Ask the LLM to select the best tool and parameters for an action.
        Returns {"tool": str, "reason": str, "parameters": dict}.
        """
        tools_desc = json.dumps({
            name: {
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for name, tool in zip(self.tools.list_tools().keys(), self.tools)
        }, indent=2)

        prompt = TOOL_SELECTION_PROMPT.format(task=action, tools=tools_desc)
        messages = [
            {"role": "system", "content": "You select tools based on task requirements."},
            {"role": "user", "content": prompt},
        ]
        response = await self._safe_chat(messages, temperature=0.3)
        self.state.tokens.add(response.usage)

        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            return {"tool": "none", "reason": "Parse failed", "parameters": {}}

    async def evaluate_result(self) -> None:
        """
        Phase 5: Result validation.
        Check whether the accumulated results satisfy the success criteria.
        This phase may trigger re-execution if results are unsatisfactory.
        """
        logger.debug("Phase 5: evaluate_result")

        if not self.state.results:
            self.state.errors.append("No results to evaluate")
            return

        success_count = sum(1 for r in self.state.results if r.get("success"))
        total = len(self.state.results)

        if success_count < total:
            logger.warning(
                "Partial success: %d/%d steps succeeded", success_count, total
            )
            self.state.errors.append(
                f"Only {success_count}/{total} steps succeeded"
            )

    async def reflect(self) -> None:
        """
        Phase 6: Reflection.
        Analyse the execution and extract lessons learned for future runs.
        """
        logger.debug("Phase 6: reflect")

        results_summary = json.dumps([
            {"step": r["step"], "success": r["success"]}
            for r in self.state.results
        ], indent=2)

        prompt = REFLECTION_PROMPT.format(
            goal=self.state.goal,
            results=results_summary,
            errors=json.dumps(self.state.errors),
        )
        messages = [
            {"role": "system", "content": "You are a reflective analyst."},
            {"role": "user", "content": prompt},
        ]

        response = await self._safe_chat(messages, temperature=0.5)
        self.state.tokens.add(response.usage)

        try:
            reflection = json.loads(response.content)
            logger.info("Reflection: %s", reflection.get("summary", ""))
        except json.JSONDecodeError:
            logger.debug("Reflection output was not valid JSON, storing raw")

    async def respond(self) -> None:
        """
        Phase 7: Final response.
        Synthesize all results into a coherent final answer for the user.
        """
        logger.debug("Phase 7: respond")

        results_text = json.dumps(self.state.results, indent=2)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Synthesize the following "
                    "task results into a clear, concise final answer for the user."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original request: {self.state.task}\n\n"
                    f"Goal: {self.state.goal}\n\n"
                    f"Results:\n{results_text}\n\n"
                    f"Provide a complete, well-formatted final answer."
                ),
            },
        ]

        response = await self._safe_chat(messages, temperature=0.5)
        self.state.tokens.add(response.usage)
        self.state.final_answer = response.content

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _safe_chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """Wrapper around LLM chat with caching, metrics, and error handling."""
        model = getattr(self.llm, "model", "unknown")
        temp = kwargs.get("temperature", 0.3)

        cached = llm_cache.get(model, messages, temp)
        if cached:
            metrics.increment("llm_cache_hit")
            logger.debug("LLM cache hit")
            return LLMResponse(content=cached, usage=LLMUsage())

        try:
            response = await self.llm.chat(messages, **kwargs)
        except Exception as e:
            error_msg = f"LLM call failed: {e}"
            logger.error(error_msg)
            self.state.errors.append(error_msg)
            metrics.increment("llm_error")
            raise

        metrics.increment(METRIC_LLM_CALLS)
        if response.usage:
            metrics.increment(METRIC_LLM_TOKENS)
            llm_cache.set(model, messages, response.content, temp)

        return response

    async def _invoke_tool(self, tool_name: str, action: str, params: Optional[dict] = None) -> str:
        """
        Look up a tool by name and invoke it.
        If params are provided, pass them as keyword arguments.
        Otherwise pass the action text as the 'action' or 'code' or 'query' parameter.
        """
        tool = self.tools.get_tool(tool_name)
        if not tool:
            raise ExecutionError(f"Tool '{tool_name}' not found in registry")

        self.state.tools_used.append(tool_name)
        logger.debug("Invoking tool '%s'", tool_name)

        try:
            if params:
                result = await tool.execute(**params)
            else:
                result = await tool.execute(action=action)
            return str(result)
        except Exception as e:
            raise ExecutionError(f"Tool '{tool_name}' failed: {e}") from e

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(ExecutionError),
    )
    async def _reasoning_step(self, action: str) -> LLMResponse:
        """Execute a reasoning-only step (no tool invocation)."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a reasoning engine. Think step by step and "
                    "produce the requested output."
                ),
            },
            {"role": "user", "content": action},
        ]
        return await self._safe_chat(messages, temperature=0.3)

    def _summary(self, elapsed: float) -> dict:
        """Build the response summary dict."""
        return {
            "task": self.state.task,
            "goal": self.state.goal,
            "plan": self.state.plan,
            "tools_used": self.state.tools_used,
            "results": self.state.results,
            "errors": self.state.errors,
            "final_answer": self.state.final_answer,
            "metadata": {
                "elapsed_seconds": round(elapsed, 2),
                "token_usage": self.state.tokens.summary(),
                "steps_total": len(self.state.plan),
                "steps_succeeded": sum(1 for r in self.state.results if r.get("success")),
            },
        }
