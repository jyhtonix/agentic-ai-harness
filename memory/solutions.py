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
               success: bool, description: str = "",
               initial_plan: Optional[list] = None,
               skills_selected: Optional[list] = None,
               actions_commands: Optional[list] = None,
               successful_techniques: Optional[list] = None,
               failed_approaches: Optional[list] = None,
               final_solution_reasoning: str = "",
               verification_result: Optional[dict] = None,
               flag_result: Optional[str] = None,
               confidence: float = 0.0,
               source_metadata: Optional[dict] = None) -> None:
        entry = {
            "challenge_id": challenge_id,
            "category": category,
            "difficulty": difficulty,
            "approach": approach,
            "tools_used": tools_used or [],
            "agents_used": agents_used or [],
            "success": success,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if source_metadata:
            entry["source_metadata"] = source_metadata
        if description:
            entry["description"] = description
        if initial_plan:
            entry["initial_plan"] = initial_plan
        if skills_selected:
            entry["skills_selected"] = skills_selected
        if actions_commands:
            entry["actions_commands"] = actions_commands
        if successful_techniques:
            entry["successful_techniques"] = successful_techniques
        if failed_approaches:
            entry["failed_approaches"] = failed_approaches
        if final_solution_reasoning:
            entry["final_solution_reasoning"] = final_solution_reasoning
        if verification_result:
            entry["verification_result"] = verification_result
        if flag_result:
            entry["flag_result"] = flag_result
        if confidence:
            entry["confidence"] = confidence
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

    def get_relevant(self, category: str, query: str = "", limit: int = 3,
                     success: Optional[bool] = True) -> list[dict]:
        """Return the most relevant prior episodes for a category.

        Scores each stored solution by keyword overlap between the current
        challenge description (query) and the stored approach, description,
        techniques and tools. Falls back to most-recent when no query.
        """
        candidates = [
            s for s in self._solutions
            if s.get("category") == category
            and (success is None or s.get("success") == success)
        ]
        if not query:
            return candidates[-limit:]

        query_terms = self._tokenize(query)
        scored = []
        for s in candidates:
            haystack = " ".join([
                s.get("approach", ""),
                s.get("description", ""),
                " ".join(s.get("successful_techniques", [])),
                " ".join(s.get("tools_used", [])),
                " ".join(s.get("skills_selected", [])),
            ])
            score = self._overlap(query_terms, self._tokenize(haystack))
            scored.append((score, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        import re
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    @staticmethod
    def _overlap(a: set, b: set) -> float:
        if not a:
            return 0.0
        return len(a & b) / len(a)

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
