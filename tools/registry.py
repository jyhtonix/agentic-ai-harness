"""
ToolRegistry — central registry for tool discovery and invocation.

Purpose: Agents discover available tools through the registry rather
than importing them directly. This decouples agent logic from tool
implementations.

Usage:
    registry = ToolRegistry()
    registry.register(FileTool())
    registry.register(WebSearchTool())

    tool = registry.get_tool("file_read")
    result = await tool.execute(path="data.txt")

    all_tools = registry.list_tools()
    definitions = registry.get_llm_definitions()  # for LLM function calling
"""

import logging
from typing import Optional

from tools.base import BaseTool

logger = logging.getLogger("tools.registry")


class ToolRegistry:
    """
    Registry of BaseTool instances. Tools are registered by their `.name`.
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        if not tool.name:
            raise ValueError("Tool must have a non-empty name")
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s — %s", tool.name, tool.description)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve a tool by name. Returns None if not found."""
        return self._tools.get(name)

    def list_tools(self) -> dict[str, str]:
        """Return {name: description} for all registered tools."""
        return {name: tool.description for name, tool in self._tools.items()}

    def get_llm_definitions(self) -> list[dict]:
        """Return OpenAI-compatible function definitions for all tools."""
        return [tool.to_llm_definition() for tool in self._tools.values()]

    def remove(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())
