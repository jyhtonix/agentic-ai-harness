import asyncio
import logging
import shlex
import subprocess
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from tools.execution.policy import ExecutionPolicy
from tools.execution.registry import ToolDefinitionRegistry

logger = logging.getLogger("tools.execution.executor")


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    BLOCKED = "BLOCKED"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"


class ToolExecutor:
    def __init__(
        self,
        registry: ToolDefinitionRegistry,
        policy: Optional[ExecutionPolicy] = None,
    ):
        self.registry = registry
        self.policy = policy or ExecutionPolicy()
        self._execution_log: list[dict] = []

    async def execute(
        self,
        tool_name: str,
        params: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        params = params or {}
        start_time = datetime.now(timezone.utc)

        entry = {
            "tool": tool_name,
            "status": ExecutionStatus.SUCCESS.value,
            "output": "",
            "error": "",
            "duration": 0.0,
            "start_time": start_time.isoformat(),
        }

        allowed, msg = self.policy.check_tool(tool_name)
        if not allowed:
            entry["status"] = ExecutionStatus.BLOCKED.value
            entry["error"] = msg
            self._execution_log.append(entry)
            return entry

        definition = self.registry.get_tool(tool_name)
        if not definition:
            entry["status"] = ExecutionStatus.TOOL_NOT_FOUND.value
            entry["error"] = f"Tool '{tool_name}' is not registered in the tool registry."
            self._execution_log.append(entry)
            return entry

        command = self._build_command(definition.command_template, params)
        allowed, msg = self.policy.check_command(command)
        if not allowed:
            entry["status"] = ExecutionStatus.BLOCKED.value
            entry["error"] = msg
            entry["command"] = command
            self._execution_log.append(entry)
            return entry

        effective_timeout = timeout or definition.timeout_seconds

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=effective_timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                entry["status"] = ExecutionStatus.TIMEOUT.value
                entry["error"] = f"Execution timed out after {effective_timeout}s"
                entry["duration"] = round(elapsed, 2)
                entry["command"] = command
                self._execution_log.append(entry)
                return entry

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            output_text = stdout.decode("utf-8", errors="replace").strip() if stdout else ""
            stderr_text = stderr.decode("utf-8", errors="replace").strip() if stderr else ""

            entry["output"] = output_text
            entry["error"] = stderr_text
            entry["duration"] = round(elapsed, 2)
            entry["command"] = command

            if proc.returncode != 0:
                entry["status"] = ExecutionStatus.FAILED.value
                if not entry["error"]:
                    entry["error"] = f"Process exited with code {proc.returncode}"

        except FileNotFoundError:
            entry["status"] = ExecutionStatus.TOOL_NOT_FOUND.value
            entry["error"] = f"Tool '{tool_name}' binary not found on the system."
            entry["duration"] = round((datetime.now(timezone.utc) - start_time).total_seconds(), 2)
        except Exception as e:
            entry["status"] = ExecutionStatus.FAILED.value
            entry["error"] = str(e)
            entry["duration"] = round((datetime.now(timezone.utc) - start_time).total_seconds(), 2)

        self._execution_log.append(entry)
        return entry

    def _build_command(self, template: str, params: dict) -> str:
        try:
            result = template.format(**params)
            return result
        except KeyError as e:
            missing = e.args[0]
            raise ValueError(f"Missing required parameter '{missing}' for command template") from e

    def get_execution_log(self) -> list[dict]:
        return list(self._execution_log)

    def clear_log(self) -> None:
        self._execution_log.clear()
