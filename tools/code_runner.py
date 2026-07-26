"""
Code execution tool.

Purpose: Runs Python code in a sandboxed environment with restricted
builtins. Blocks dangerous modules (os, subprocess, socket, etc.) to
prevent abuse while allowing safe computations.

Clean architecture: Encapsulates sandboxing logic behind a simple
run() function. Agents can execute code without managing subprocesses
or security concerns.
"""

import ast
import sys
import builtins
from io import StringIO

# Builtins available inside the sandbox.
SAFE_BUILTINS = {
    "abs", "all", "any", "bin", "bool", "chr", "complex", "dict",
    "divmod", "enumerate", "filter", "float", "format", "frozenset",
    "hex", "int", "isinstance", "issubclass", "iter", "len", "list",
    "map", "max", "min", "next", "oct", "ord", "pow", "print",
    "range", "repr", "reversed", "round", "set", "slice", "sorted",
    "str", "sum", "tuple", "type", "zip", "True", "False", "None",
}

BLOCKED_MODULES = {"os", "subprocess", "shutil", "sys", "socket", "ctypes", "importlib"}


def _validate(code: str):
    """Check code for blocked imports before execution."""
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


async def run(code: str) -> dict:
    """
    Execute Python code in a sandbox.
    Returns {"stdout": str, "stderr": str}.
    """
    _validate(code)

    stdout_buf = StringIO()
    stderr_buf = StringIO()
    old_stdout, old_stderr = sys.stdout, sys.stderr

    safe_builtins = {name: getattr(builtins, name) for name in SAFE_BUILTINS if hasattr(builtins, name)}

    try:
        sys.stdout, sys.stderr = stdout_buf, stderr_buf
        exec(code, {"__builtins__": safe_builtins})
    except Exception as e:
        stderr_buf.write(f"{type(e).__name__}: {e}")
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    return {"stdout": stdout_buf.getvalue(), "stderr": stderr_buf.getvalue()}
