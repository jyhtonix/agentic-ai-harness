import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("memory.strategies")


class StrategyMemory:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or (Path.cwd() / "memory" / "strategies"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._strategies: dict[str, list[dict]] = {}
        self._load()

    def record(self, category: str, strategy: str, confidence: float = 0.5) -> None:
        if category not in self._strategies:
            self._strategies[category] = []
        entry = {
            "strategy": strategy,
            "confidence": confidence,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        for existing in self._strategies[category]:
            if existing["strategy"] == strategy:
                existing["confidence"] = max(existing["confidence"], confidence)
                existing["recorded_at"] = entry["recorded_at"]
                self._save()
                return
        self._strategies[category].append(entry)
        self._save()

    def get_strategies(self, category: str) -> list[str]:
        entries = self._strategies.get(category, [])
        sorted_entries = sorted(entries, key=lambda x: x["confidence"], reverse=True)
        return [e["strategy"] for e in sorted_entries]

    def get_best(self, category: str) -> Optional[str]:
        entries = self._strategies.get(category, [])
        if not entries:
            return None
        best = max(entries, key=lambda x: x["confidence"])
        return best["strategy"]

    def get_all(self) -> dict[str, list[dict]]:
        return dict(self._strategies)

    def _save(self) -> None:
        path = self.storage_dir / "strategies.json"
        with open(path, "w") as f:
            json.dump(self._strategies, f, indent=2)

    def _load(self) -> None:
        path = self.storage_dir / "strategies.json"
        if path.exists():
            try:
                with open(path) as f:
                    self._strategies = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._strategies = {}
