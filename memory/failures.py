import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("memory.failures")


class FailureMemory:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or (Path.cwd() / "memory" / "failures"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._failures: list[dict] = []
        self._load()

    def record(self, challenge_id: str, category: str, reason: str,
               failure_type: str, recommendation: str = "") -> None:
        entry = {
            "challenge_id": challenge_id,
            "category": category,
            "reason": reason,
            "failure_type": failure_type,
            "recommendation": recommendation,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._failures.append(entry)
        self._save()

    def get_failures(self, category: Optional[str] = None) -> list[dict]:
        if category is None:
            return list(self._failures)
        return [f for f in self._failures if f.get("category") == category]

    def get_common_failures(self, top_n: int = 5) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for f in self._failures:
            ft = f.get("failure_type", "unknown")
            counts[ft] = counts.get(ft, 0) + 1
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_counts[:top_n]

    def get_recommendations(self) -> list[str]:
        seen = set()
        recs = []
        for f in self._failures:
            r = f.get("recommendation", "")
            if r and r not in seen:
                seen.add(r)
                recs.append(r)
        return recs

    def clear(self) -> None:
        self._failures.clear()
        self._save()

    def _save(self) -> None:
        path = self.storage_dir / "failures.json"
        with open(path, "w") as f:
            json.dump(self._failures, f, indent=2)

    def _load(self) -> None:
        path = self.storage_dir / "failures.json"
        if path.exists():
            try:
                with open(path) as f:
                    self._failures = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._failures = []
