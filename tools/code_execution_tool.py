"""
CodeExecutionTool — sandboxed Python code execution.

Executes Python code in a restricted environment:
  - Only safe builtins are available (print, len, range, etc.)
  - Dangerous modules (os, subprocess, socket) are blocked
  - AST-level validation catches unsafe imports before execution
  - stdout and stderr are captured separately
"""

import ast
import sys
import builtins
from io import StringIO

from tools.base import BaseTool

SAFE_BUILTINS = {
    "abs", "all", "any", "bin", "bool", "chr", "complex", "dict",
    "divmod", "enumerate", "filter", "float", "format", "frozenset",
    "hex", "int", "isinstance", "issubclass", "iter", "len", "list",
    "map", "max", "min", "next", "oct", "ord", "pow", "print",
    "range", "repr", "reversed", "round", "set", "slice", "sorted",
    "str", "sum", "tuple", "type", "zip", "True", "False", "None",
}

BLOCKED_MODULES = {"os", "subprocess", "shutil", "sys", "socket", "ctypes", "importlib"}


class CodeExecutionTool(BaseTool):
    name = "code_execute"
    description = "Execute Python code safely in a sandboxed environment. Returns stdout and stderr."
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute",
            },
        },
        "required": ["code"],
    }

    async def execute(self, code: str) -> str:
        self._validate(code)

        stdout_buf = StringIO()
        stderr_buf = StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr

        safe_builtins = {
            name: getattr(builtins, name)
            for name in SAFE_BUILTINS if hasattr(builtins, name)
        }

        try:
            sys.stdout, sys.stderr = stdout_buf, stderr_buf
            exec(code, {"__builtins__": safe_builtins})
        except Exception as e:
            stderr_buf.write(f"{type(e).__name__}: {e}")
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        out = stdout_buf.getvalue()
        err = stderr_buf.getvalue()
        parts = []
        if out:
            parts.append(f"[stdout]\n{out}")
        if err:
            parts.append(f"[stderr]\n{err}")
        return "\n".join(parts) if parts else "[no output]"

    def _validate(self, code: str):
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise ValueError(f"Syntax error: {e}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in BLOCKED_MODULES:
                        raise PermissionError(f"Import not allowed: {alias.name}")
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in BLOCKED_MODULES:
                    raise PermissionError(f"Import not allowed: {node.module}")
