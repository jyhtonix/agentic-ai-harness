"""
Filesystem tool.

Purpose: Provides safe, sandboxed file read/write/list operations.
All paths are resolved relative to a workspace root to prevent
path traversal attacks.

Clean architecture: This is a gateway (interface adapter). The
tool system wraps external I/O behind a simple interface so
agents never touch the filesystem directly.
"""

import os
from pathlib import Path

# All file operations are locked to this directory.
WORKSPACE = Path.cwd() / "workspace"


def _resolve(relative_path: str) -> Path:
    """Resolve a relative path within the workspace, preventing traversal."""
    full = (WORKSPACE / relative_path).resolve()
    if not str(full).startswith(str(WORKSPACE.resolve())):
        raise PermissionError(f"Path traversal denied: {relative_path}")
    return full


def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    full = _resolve(path)
    if not full.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return full.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed."""
    full = _resolve(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return f"Written {len(content)} bytes to {path}"


def list_files(path: str = "") -> list[str]:
    """List entries in a directory. Dirs get a trailing slash."""
    target = _resolve(path) if path else WORKSPACE
    if not target.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    return [
        f"{entry.name}/" if entry.is_dir() else entry.name
        for entry in sorted(target.iterdir())
    ]
