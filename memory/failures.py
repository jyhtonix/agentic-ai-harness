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
               failure_type: str, recommendation: str = "",
               description: str = "",
               initial_plan: Optional[list] = None,
               skills_selected: Optional[list] = None,
               tools_used: Optional[list] = None,
               actions_commands: Optional[list] = None,
               failed_approaches: Optional[list] = None,
               final_solution_reasoning: str = "",
               verification_result: Optional[dict] = None,
               flag_result: Optional[str] = None) -> None:
        entry = {
            "challenge_id": challenge_id,
            "category": category,
            "reason": reason,
            "failure_type": failure_type,
            "recommendation": recommendation,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if description:
            entry["description"] = description
        if initial_plan:
            entry["initial_plan"] = initial_plan
        if skills_selected:
            entry["skills_selected"] = skills_selected
        if tools_used:
            entry["tools_used"] = tools_used
        if actions_commands:
            entry["actions_commands"] = actions_commands
        if failed_approaches:
            entry["failed_approaches"] = failed_approaches
        if final_solution_reasoning:
            entry["final_solution_reasoning"] = final_solution_reasoning
        if verification_result:
            entry["verification_result"] = verification_result
        if flag_result:
            entry["flag_result"] = flag_result
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

    def get_relevant(self, category: str, query: str = "", limit: int = 3) -> list[dict]:
        """Return the most relevant prior failure episodes for a category."""
        import re

        def tokenize(text: str) -> set[str]:
            return set(re.findall(r"[a-z0-9]+", text.lower()))

        def overlap(a: set, b: set) -> float:
            if not a:
                return 0.0
            return len(a & b) / len(a)

        candidates = [f for f in self._failures if f.get("category") == category]
        if not query:
            return candidates[-limit:]

        query_terms = tokenize(query)
        scored = []
        for f in candidates:
            haystack = " ".join([
                f.get("reason", ""),
                f.get("recommendation", ""),
                " ".join(f.get("failed_approaches", [])),
                " ".join(f.get("tools_used", [])),
            ])
            score = overlap(query_terms, tokenize(haystack))
            scored.append((score, f))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:limit]]

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
