import logging
import os
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("tools.execution.registry")


class ToolDefinition:
    def __init__(self, data: dict):
        self.name: str = data["name"]
        self.description: str = data.get("description", "")
        self.category: str = data.get("category", "")
        self.purpose: str = data.get("purpose", "")
        self.input_types: list = data.get("input_types", [])
        self.output_types: list = data.get("output_types", [])
        self.risk_level: str = data.get("risk_level", "low")
        self.execution_method: str = data.get("execution_method", "subprocess")
        self.command_template: str = data.get("command_template", "")
        self.timeout_seconds: int = data.get("timeout_seconds", 30)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "purpose": self.purpose,
            "input_types": list(self.input_types),
            "output_types": list(self.output_types),
            "risk_level": self.risk_level,
            "execution_method": self.execution_method,
            "command_template": self.command_template,
            "timeout_seconds": self.timeout_seconds,
        }

    def __repr__(self):
        return f"ToolDefinition(name='{self.name}', category='{self.category}')"


class ToolDefinitionRegistry:
    REQUIRED_FIELDS = {"name", "description", "category"}

    def __init__(self, definitions_dir: Optional[str] = None):
        self._definitions: dict[str, ToolDefinition] = {}
        self._definitions_dir = definitions_dir or self._default_definitions_dir()

    @staticmethod
    def _default_definitions_dir() -> str:
        dir_path = Path(__file__).parent / "definitions"
        return str(dir_path.resolve())

    def discover(self) -> list[ToolDefinition]:
        self._definitions = {}
        base = Path(self._definitions_dir)
        if not base.exists():
            logger.warning("Definitions directory does not exist: %s", base)
            return []

        loaded = []
        for entry in sorted(base.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            tool_yaml = entry / "tool.yaml"
            if not tool_yaml.exists():
                continue
            try:
                with open(tool_yaml, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    logger.warning("Invalid tool.yaml (not a dict): %s", tool_yaml)
                    continue
                tools_list = data.get("tools", [])
                if not isinstance(tools_list, list):
                    logger.warning("Invalid tool.yaml (tools is not a list): %s", tool_yaml)
                    continue
                for item in tools_list:
                    if not self._validate(item, tool_yaml):
                        continue
                    definition = ToolDefinition(item)
                    self._definitions[definition.name] = definition
                    loaded.append(definition)
                    logger.info("Discovered tool: %s (%s)", definition.name, definition.category)
            except yaml.YAMLError as e:
                logger.warning("YAML parse error in %s: %s", tool_yaml, e)
            except OSError as e:
                logger.warning("Cannot read %s: %s", tool_yaml, e)

        return loaded

    def _validate(self, item: dict, path: Path) -> bool:
        missing = self.REQUIRED_FIELDS - set(item.keys())
        if missing:
            logger.warning("Tool in %s missing required fields: %s", path, missing)
            return False
        return True

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._definitions.get(name)

    def get_tools(self, category: Optional[str] = None) -> list[ToolDefinition]:
        if category is None:
            return list(self._definitions.values())
        return [t for t in self._definitions.values() if t.category == category]

    def list_categories(self) -> list[str]:
        cats = sorted({t.category for t in self._definitions.values()})
        return cats

    def __contains__(self, name: str) -> bool:
        return name in self._definitions

    def __len__(self) -> int:
        return len(self._definitions)

    def __iter__(self):
        return iter(self._definitions.values())
