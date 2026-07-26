"""
BaseTool — abstract interface for all tools.

Purpose: Every tool in the system follows this contract. Tools are the
capabilities agents use to interact with the world — reading files,
searching the web, executing code, querying databases.

Usage:
    class MyTool(BaseTool):
        name = "my_tool"
        description = "Does something useful"
        parameters = {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }

        async def execute(self, input: str) -> str:
            return f"processed: {input}"
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseTool(ABC):
    """
    Abstract base for all tools.

    Subclasses must set:
        name        — unique identifier (e.g. "file_read")
        description — what the tool does (for LLM selection)
        parameters  — JSON schema describing expected arguments

    Subclasses must implement:
        execute()   — the actual tool logic
    """

    name: str = ""
    description: str = ""
    parameters: dict = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool with the given keyword arguments.
        Returns the result (str, dict, list, etc.).
        """
        ...

    def to_llm_definition(self) -> dict:
        """Return an OpenAI-compatible function definition for LLM tool calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
