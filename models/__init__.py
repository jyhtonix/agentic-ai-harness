"""Model configuration registry.

Loads model profiles from YAML config files and provides
lookup by model name or ID.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("models.registry")


class ModelConfig:
    def __init__(self, name: str, provider: str, model_id: str,
                 temperature: float = 0.3, max_tokens: int = 4096,
                 available_tools: Optional[list[str]] = None,
                 notes: str = ""):
        self.name = name
        self.provider = provider
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.available_tools = available_tools or []
        self.notes = notes

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "provider": self.provider,
            "model_id": self.model_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "available_tools": list(self.available_tools),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModelConfig":
        return cls(
            name=d["name"],
            provider=d.get("provider", ""),
            model_id=d.get("model_id", d["name"]),
            temperature=d.get("temperature", 0.3),
            max_tokens=d.get("max_tokens", 4096),
            available_tools=d.get("available_tools", []),
            notes=d.get("notes", ""),
        )


class ModelRegistry:
    def __init__(self, models_dir: Optional[str] = None):
        self._models: dict[str, ModelConfig] = {}
        self._by_name: dict[str, ModelConfig] = {}
        self._models_dir = Path(models_dir or (Path.cwd() / "models"))
        self._discover()

    def _discover(self) -> None:
        if not self._models_dir.exists():
            logger.warning("Models directory not found: %s", self._models_dir)
            return
        for f in sorted(self._models_dir.glob("*.yaml")):
            try:
                with open(f) as fh:
                    data = yaml.safe_load(fh)
                if isinstance(data, dict) and "name" in data:
                    config = ModelConfig.from_dict(data)
                    self._models[config.model_id] = config
                    self._by_name[config.name] = config
                    logger.info("Loaded model: %s (%s)", config.name, config.model_id)
            except (yaml.YAMLError, OSError, KeyError) as e:
                logger.warning("Cannot load model config %s: %s", f.name, e)

    def get(self, model_id: str) -> Optional[ModelConfig]:
        return self._models.get(model_id)

    def get_by_name(self, name: str) -> Optional[ModelConfig]:
        return self._by_name.get(name)

    def list_models(self) -> list[str]:
        return [m.name for m in self._models.values()]

    def list_ids(self) -> list[str]:
        return list(self._models.keys())

    def all(self) -> dict[str, ModelConfig]:
        return dict(self._models)

    def register(self, config: ModelConfig) -> None:
        self._models[config.model_id] = config
        self._by_name[config.name] = config
        logger.info("Registered model: %s", config.name)

    def __contains__(self, model_id: str) -> bool:
        return model_id in self._models

    def __len__(self) -> int:
        return len(self._models)
