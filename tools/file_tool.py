"""
FileTool — safe filesystem operations.

Provides three operations under a single tool, dispatched via the
`action` parameter:
  - read:    return file contents
  - write:   write content to a file
  - list:    list directory entries

All paths are sandboxed to a workspace directory to prevent traversal.
"""

import json
from pathlib import Path

from tools.base import BaseTool

WORKSPACE = Path.cwd() / "workspace"


def _resolve(relative_path: str) -> Path:
    full = (WORKSPACE / relative_path).resolve()
    if not str(full).startswith(str(WORKSPACE.resolve())):
        raise PermissionError(f"Path traversal denied: {relative_path}")
    return full


class FileTool(BaseTool):
    name = "file"
    description = "Read, write, or list files in the workspace. Actions: read, write, list."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "list"],
                "description": "Operation to perform",
            },
            "path": {
                "type": "string",
                "description": "Relative file or directory path",
            },
            "content": {
                "type": "string",
                "description": "Content to write (required for write action)",
            },
        },
        "required": ["action", "path"],
    }

    async def execute(self, action: str, path: str, content: str = "") -> str:
        if action == "read":
            return self._read(path)
        elif action == "write":
            return self._write(path, content)
        elif action == "list":
            return json.dumps(self._list(path), indent=2)
        else:
            raise ValueError(f"Unknown action: {action}")

    def _read(self, path: str) -> str:
        full = _resolve(path)
        if not full.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return full.read_text(encoding="utf-8")

    def _write(self, path: str, content: str) -> str:
        full = _resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"

    def _list(self, path: str) -> list[str]:
        target = _resolve(path) if path else WORKSPACE
        if not target.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        return [
            f"{entry.name}/" if entry.is_dir() else entry.name
            for entry in sorted(target.iterdir())
        ]
