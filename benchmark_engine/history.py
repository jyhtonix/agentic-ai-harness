from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from benchmark_engine.results import BenchmarkResult

logger = logging.getLogger("benchmark_engine.history")


class BenchmarkHistory:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or self._default_dir())
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _default_dir() -> str:
        return str(Path.cwd() / "benchmark" / "history")

    def save(self, result: BenchmarkResult) -> str:
        filename = f"{result.challenge_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        path = self.storage_dir / filename
        with open(path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info("Saved benchmark result: %s", filename)
        return str(path)

    def save_batch(self, results: list[BenchmarkResult]) -> list[str]:
        paths = []
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        for i, r in enumerate(results):
            filename = f"batch_{timestamp}_{i}_{r.challenge_id}.json"
            path = self.storage_dir / filename
            with open(path, "w") as f:
                json.dump(r.to_dict(), f, indent=2)
            paths.append(str(path))
            logger.debug("Saved batch result: %s", filename)
        return paths

    def load(self, filename: str) -> Optional[BenchmarkResult]:
        path = self.storage_dir / filename
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return BenchmarkResult.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Cannot load %s: %s", filename, e)
            return None

    def load_all(self) -> list[BenchmarkResult]:
        results = []
        for f in sorted(self.storage_dir.glob("*.json")):
            result = self.load(f.name)
            if result:
                results.append(result)
        return results

    def list_sessions(self) -> list[dict]:
        sessions = []
        for f in self.storage_dir.glob("*.json"):
            sessions.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        return sorted(sessions, key=lambda x: x["modified"], reverse=True)

    def get_statistics(self) -> dict:
        results = self.load_all()
        if not results:
            return {"total": 0, "solved": 0, "datasets": {}}

        solved = sum(1 for r in results if r.solved)
        return {
            "total": len(results),
            "solved": solved,
            "success_rate": round(solved / len(results), 3) if results else 0,
            "datasets": {},
        }
