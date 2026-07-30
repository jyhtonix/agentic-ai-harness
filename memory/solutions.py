import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("memory.solutions")


class SolutionMemory:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or (Path.cwd() / "memory" / "solutions"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._solutions: list[dict] = []
        self._load()

    def record(self, challenge_id: str, category: str, difficulty: str,
               approach: str, tools_used: list[str], agents_used: list[str],
               success: bool) -> None:
        entry = {
            "challenge_id": challenge_id,
            "category": category,
            "difficulty": difficulty,
            "approach": approach,
            "tools_used": tools_used,
            "agents_used": agents_used,
            "success": success,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._solutions.append(entry)
        self._save()

    def get_solutions(self, category: Optional[str] = None, success: Optional[bool] = None) -> list[dict]:
        results = list(self._solutions)
        if category:
            results = [s for s in results if s.get("category") == category]
        if success is not None:
            results = [s for s in results if s.get("success") == success]
        return results

    def get_successful_approaches(self, category: str) -> list[str]:
        approaches = []
        for s in self._solutions:
            if s.get("category") == category and s.get("success"):
                approaches.append(s.get("approach", ""))
        seen = set()
        unique = []
        for a in approaches:
            if a not in seen:
                seen.add(a)
                unique.append(a)
        return unique

    def clear(self) -> None:
        self._solutions.clear()
        self._save()

    def _save(self) -> None:
        path = self.storage_dir / "solutions.json"
        with open(path, "w") as f:
            json.dump(self._solutions, f, indent=2)

    def _load(self) -> None:
        path = self.storage_dir / "solutions.json"
        if path.exists():
            try:
                with open(path) as f:
                    self._solutions = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._solutions = []
