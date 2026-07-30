"""Dataset loader for benchmark challenges.

Supports loading challenge definitions from the benchmark/datasets/ catalog.
Works alongside the existing ChallengeLoader for maximum flexibility.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("benchmark_engine.dataset")


class DatasetLoader:
    def __init__(self, datasets_dir: Optional[str] = None):
        self.datasets_dir = Path(datasets_dir or (Path.cwd() / "benchmark" / "datasets"))

    def list_datasets(self) -> list[str]:
        if not self.datasets_dir.exists():
            return []
        datasets = []
        for f in self.datasets_dir.glob("*.yaml"):
            datasets.append(f.stem)
        return sorted(datasets)

    def load_dataset(self, name: str) -> list[dict]:
        path = self.datasets_dir / f"{name}.yaml"
        if not path.exists():
            logger.warning("Dataset not found: %s", path)
            return []
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data or not isinstance(data, dict):
                return []
            return data.get("challenges", [])
        except (yaml.YAMLError, OSError) as e:
            logger.warning("Cannot load dataset %s: %s", name, e)
            return []

    def get_challenge_ids(self, dataset_name: str) -> list[str]:
        challenges = self.load_dataset(dataset_name)
        return [c.get("id", "") for c in challenges if c.get("id")]

    def get_categories(self, dataset_name: str) -> dict[str, list[str]]:
        categories: dict[str, list[str]] = {}
        for c in self.load_dataset(dataset_name):
            cat = c.get("category", "unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(c.get("id", ""))
        return categories
