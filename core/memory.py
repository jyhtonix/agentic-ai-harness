"""
Memory system for the Agent Harness.

Three-tier architecture:
  WorkingMemory   — ephemeral, in-memory (current task, conversation, context)
  LongTermMemory  — persistent, PostgreSQL (tasks, solutions, preferences, knowledge)
  VectorMemory    — semantic search via embeddings (numpy cosine similarity)

  MemoryManager   — facade coordinating all three stores

Workflow:
  1. on_new_task()     — search previous knowledge, add relevant context
  2. retrieve_context() — format context for the agent prompt
  3. on_task_complete() — save successful result across all stores
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sqlalchemy import or_, select

from models.embeddings import Embedder

logger = logging.getLogger("core.memory")


# ---------------------------------------------------------------------------
# Working Memory
# ---------------------------------------------------------------------------


@dataclass
class WorkingMemory:
    """
    Ephemeral, in-memory storage for the current session.
    Holds the current task, conversation history, and temporary context.
    """

    current_task: str = ""
    goal: str = ""
    conversation: list[dict] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    start_time: float = 0.0

    def set_task(self, task: str, goal: str = "") -> None:
        self.current_task = task
        self.goal = goal
        self.start_time = time.time()

    def get_task(self) -> str:
        return self.current_task

    def add_message(self, role: str, content: str) -> None:
        self.conversation.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_history(self, limit: int = 0) -> list[dict]:
        if limit > 0:
            return self.conversation[-limit:]
        return list(self.conversation)

    def set_context(self, key: str, value) -> None:
        self.context[key] = value

    def get_context(self, key: str, default=None):
        return self.context.get(key, default)

    def clear(self) -> None:
        self.current_task = ""
        self.goal = ""
        self.conversation.clear()
        self.context.clear()
        self.start_time = 0.0

    def snapshot(self) -> dict:
        return {
            "current_task": self.current_task,
            "goal": self.goal,
            "conversation": list(self.conversation),
            "context_keys": list(self.context.keys()),
            "elapsed": time.time() - self.start_time if self.start_time else 0,
        }


# ---------------------------------------------------------------------------
# Long-Term Memory (PostgreSQL)
# ---------------------------------------------------------------------------


class LongTermMemory:
    """
    Persistent storage for tasks, solutions, user preferences, and knowledge.
    Uses PostgreSQL via SQLAlchemy async sessions.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    # -- Tasks -----------------------------------------------------------

    async def save_task(self, task: str, result: str = "",
                        success: bool = True,
                        metadata: Optional[dict] = None) -> int:
        from database.models import TaskMemory as TaskModel
        async with self._session_factory() as session:
            record = TaskModel(
                task_description=task,
                result=result,
                success=success,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record.id

    async def search_tasks(self, query: str, limit: int = 10) -> list[dict]:
        from database.models import TaskMemory as TaskModel
        async with self._session_factory() as session:
            stmt = (
                select(TaskModel)
                .where(
                    or_(
                        TaskModel.task_description.ilike(f"%{query}%"),
                        TaskModel.result.ilike(f"%{query}%"),
                    )
                )
                .order_by(TaskModel.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": r.id,
                    "task": r.task_description,
                    "result": r.result or "",
                    "goal": r.goal or "",
                    "success": r.success,
                    "metadata": json.loads(r.metadata_json) if r.metadata_json else {},
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

    async def get_task(self, task_id: int) -> Optional[dict]:
        from database.models import TaskMemory as TaskModel
        async with self._session_factory() as session:
            record = await session.get(TaskModel, task_id)
            if not record:
                return None
            return {
                "id": record.id,
                "task": record.task_description,
                "result": record.result or "",
                "goal": record.goal or "",
                "success": record.success,
                "metadata": json.loads(record.metadata_json) if record.metadata_json else {},
                "created_at": record.created_at.isoformat() if record.created_at else "",
            }

    # -- Solutions -------------------------------------------------------

    async def save_solution(self, problem: str, solution: str,
                            patterns: Optional[list[str]] = None,
                            rating: float = 1.0) -> int:
        from database.models import SolutionMemory as SolutionModel
        async with self._session_factory() as session:
            record = SolutionModel(
                problem=problem,
                solution=solution,
                patterns_used=", ".join(patterns) if patterns else None,
                success_rating=rating,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record.id

    async def search_solutions(self, query: str, limit: int = 10) -> list[dict]:
        from database.models import SolutionMemory as SolutionModel
        async with self._session_factory() as session:
            stmt = (
                select(SolutionModel)
                .where(
                    or_(
                        SolutionModel.problem.ilike(f"%{query}%"),
                        SolutionModel.solution.ilike(f"%{query}%"),
                        SolutionModel.patterns_used.ilike(f"%{query}%"),
                    )
                )
                .order_by(SolutionModel.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": r.id,
                    "problem": r.problem,
                    "solution": r.solution,
                    "patterns": r.patterns_used.split(", ") if r.patterns_used else [],
                    "rating": r.success_rating,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

    # -- User Preferences ------------------------------------------------

    async def set_preference(self, user_id: str, key: str, value: str) -> None:
        from database.models import UserPreference as PrefModel
        async with self._session_factory() as session:
            stmt = select(PrefModel).where(
                PrefModel.user_id == user_id,
                PrefModel.key == key,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                session.add(PrefModel(user_id=user_id, key=key, value=value))
            await session.commit()

    async def get_preference(self, user_id: str, key: str) -> Optional[str]:
        from database.models import UserPreference as PrefModel
        async with self._session_factory() as session:
            stmt = select(PrefModel).where(
                PrefModel.user_id == user_id,
                PrefModel.key == key,
            )
            record = (await session.execute(stmt)).scalar_one_or_none()
            return record.value if record else None

    async def get_all_preferences(self, user_id: str) -> dict[str, str]:
        from database.models import UserPreference as PrefModel
        async with self._session_factory() as session:
            stmt = select(PrefModel).where(PrefModel.user_id == user_id)
            rows = (await session.execute(stmt)).scalars().all()
            return {r.key: r.value for r in rows}

    # -- Knowledge -------------------------------------------------------

    async def save_knowledge(self, topic: str, content: str,
                             source: str = "",
                             tags: Optional[list[str]] = None) -> int:
        from database.models import KnowledgeEntry as KnowledgeModel
        async with self._session_factory() as session:
            record = KnowledgeModel(
                topic=topic,
                content=content,
                source=source or None,
                tags=", ".join(tags) if tags else None,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record.id

    async def search_knowledge(self, query: str, limit: int = 10) -> list[dict]:
        from database.models import KnowledgeEntry as KnowledgeModel
        async with self._session_factory() as session:
            stmt = (
                select(KnowledgeModel)
                .where(
                    or_(
                        KnowledgeModel.topic.ilike(f"%{query}%"),
                        KnowledgeModel.content.ilike(f"%{query}%"),
                        KnowledgeModel.tags.ilike(f"%{query}%"),
                    )
                )
                .order_by(KnowledgeModel.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": r.id,
                    "topic": r.topic,
                    "content": r.content,
                    "source": r.source or "",
                    "tags": r.tags.split(", ") if r.tags else [],
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

    # -- Generic delete --------------------------------------------------

    async def delete(self, table: str, record_id: int) -> bool:
        from database.models import (
            KnowledgeEntry as KModel,
            SolutionMemory as SModel,
            TaskMemory as TModel,
            UserPreference as PModel,
        )
        model_map = {
            "task": TModel,
            "solution": SModel,
            "preference": PModel,
            "knowledge": KModel,
        }
        model_cls = model_map.get(table)
        if not model_cls:
            return False
        async with self._session_factory() as session:
            record = await session.get(model_cls, record_id)
            if not record:
                return False
            await session.delete(record)
            await session.commit()
            return True


# ---------------------------------------------------------------------------
# Vector Memory (semantic search)
# ---------------------------------------------------------------------------


@dataclass
class VectorEntry:
    id: str
    content: str
    embedding: list[float]
    metadata: dict
    score: float = 0.0


class VectorMemory:
    """
    In-memory vector store using cosine similarity via numpy.
    For production, swap with a pgvector-backed implementation.
    """

    def __init__(self, embedder: Embedder):
        self._entries: list[VectorEntry] = []
        self._embedder = embedder
        self._next_id = 0

    async def store(self, content: str,
                    metadata: Optional[dict] = None,
                    embedding: Optional[list[float]] = None) -> str:
        if embedding is None:
            embedding = await self._embedder.embed(content)
        entry_id = f"vec_{self._next_id}"
        self._next_id += 1
        self._entries.append(VectorEntry(
            id=entry_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
        ))
        return entry_id

    async def search(self, query: str, limit: int = 5) -> list[VectorEntry]:
        query_embedding = await self._embedder.embed(query)
        return await self._search_vector(query_embedding, limit)

    async def search_by_vector(self, query_embedding: list[float],
                               limit: int = 5) -> list[VectorEntry]:
        return await self._search_vector(query_embedding, limit)

    async def _search_vector(self, query_embedding: list[float],
                             limit: int) -> list[VectorEntry]:
        if not self._entries:
            return []
        query_np = np.array(query_embedding, dtype=np.float32)
        query_norm = query_np / (np.linalg.norm(query_np) + 1e-10)
        for entry in self._entries:
            entry_np = np.array(entry.embedding, dtype=np.float32)
            entry_norm = entry_np / (np.linalg.norm(entry_np) + 1e-10)
            entry.score = float(np.dot(query_norm, entry_norm))
        results = sorted(self._entries, key=lambda x: x.score, reverse=True)
        return results[:limit]

    async def delete(self, entry_id: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        return len(self._entries) < before

    def count(self) -> int:
        return len(self._entries)

    async def clear(self) -> None:
        self._entries.clear()


# ---------------------------------------------------------------------------
# MemoryManager (facade)
# ---------------------------------------------------------------------------


class MemoryManager:
    """
    Facade that coordinates Working, Long-Term, and Vector memory stores.

    Workflow when a new task arrives:
      1. Search previous knowledge (vector + relational)
      2. Add relevant context
      3. Execute task
      4. Save successful result
    """

    def __init__(self,
                 working: Optional[WorkingMemory] = None,
                 long_term: Optional[LongTermMemory] = None,
                 vector: Optional[VectorMemory] = None):
        self.working = working or WorkingMemory()
        self.long_term = long_term
        self.vector = vector

    # ------------------------------------------------------------------
    # Skill memory
    # ------------------------------------------------------------------

    @staticmethod
    def _skill_text_for_embedding(skill: dict) -> str:
        fm = skill.get("frontmatter", {})
        parts = [
            fm.get("name", ""),
            fm.get("description", ""),
            fm.get("subdomain", ""),
            " ".join(fm.get("tags", [])),
        ]
        return " | ".join(p for p in parts if p)

    async def store_skill_embedding(self, skill: dict) -> Optional[str]:
        if not self.vector:
            return None
        text = self._skill_text_for_embedding(skill)
        fm = skill.get("frontmatter", {})
        meta = {
            "type": "skill",
            "name": fm.get("name", ""),
            "subdomain": fm.get("subdomain", ""),
            "tags": fm.get("tags", []),
            "path": skill.get("metadata", {}).get("path", ""),
        }
        return await self.vector.store(content=text, metadata=meta)

    async def store_all_skill_embeddings(self, skills: list[dict]) -> int:
        count = 0
        for skill in skills:
            eid = await self.store_skill_embedding(skill)
            if eid:
                count += 1
        return count

    async def search_skills(self, query: str, limit: int = 5) -> list[dict]:
        if not self.vector:
            return []
        results = await self.vector.search(query, limit=limit * 3)
        skill_results = [r for r in results if r.metadata.get("type") == "skill"]
        return [
            {
                "name": r.metadata.get("name", ""),
                "subdomain": r.metadata.get("subdomain", ""),
                "tags": r.metadata.get("tags", []),
                "path": r.metadata.get("path", ""),
                "score": round(r.score, 4),
            }
            for r in skill_results[:limit]
        ]

    # ------------------------------------------------------------------
    # Core workflow
    # ------------------------------------------------------------------

    async def on_new_task(self, task: str, goal: str = "",
                          user_id: str = "") -> dict:
        """
        Called when a new task arrives:
          1. Set current task in working memory
          2. Search for relevant context
          3. Return context dict
        """
        self.working.set_task(task, goal)

        search_results = await self._search_all(task, limit=5)

        relevant_context = {
            "previous_tasks": [],
            "solutions": [],
            "knowledge": [],
            "preferences": {},
        }

        for item in search_results:
            mtype = item.get("type", "")
            if mtype == "task" and len(relevant_context["previous_tasks"]) < 3:
                relevant_context["previous_tasks"].append(item)
            elif mtype == "solution" and len(relevant_context["solutions"]) < 3:
                relevant_context["solutions"].append(item)
            elif mtype == "knowledge" and len(relevant_context["knowledge"]) < 3:
                relevant_context["knowledge"].append(item)

        if user_id and self.long_term:
            relevant_context["preferences"] = await self.long_term.get_all_preferences(user_id)

        context_str = self._format_context(relevant_context)
        self.working.set_context("retrieved_context", context_str)
        self.working.set_context("search_results", relevant_context)

        self.working.add_message("system", f"Context loaded for task: {task}")

        return relevant_context

    async def on_task_complete(self, task: str, result: str,
                               success: bool = True,
                               patterns: Optional[list[str]] = None,
                               metadata: Optional[dict] = None) -> None:
        """
        Called after task execution:
          1. Save to long-term task memory
          2. Save as knowledge entry
          3. Store embedding for future retrieval
        """
        self.working.add_message("system", "Task completed")

        if self.long_term:
            await self.long_term.save_task(
                task=task, result=result, success=success, metadata=metadata,
            )
            if success and result:
                await self.long_term.save_solution(
                    problem=task, solution=result,
                    patterns=patterns, rating=1.0,
                )
                await self.long_term.save_knowledge(
                    topic=task[:100], content=result,
                    source="agent_execution", tags=patterns,
                )

        if self.vector and success and result:
            meta = {"type": "task_result", "task": task, "success": success}
            if patterns:
                meta["patterns"] = patterns
            if metadata:
                meta.update(metadata)
            await self.vector.store(content=result, metadata=meta)

    # ------------------------------------------------------------------
    # Memory operations
    # ------------------------------------------------------------------

    async def save_memory(self, storage: str, key: str, data) -> None:
        if storage == "working":
            self.working.set_context(key, data)
        elif storage == "preference" and self.long_term:
            user_id = data.get("user_id", "") if isinstance(data, dict) else ""
            value = data.get("value", str(data)) if isinstance(data, dict) else str(data)
            await self.long_term.set_preference(user_id, key, value)
        elif storage == "knowledge" and self.long_term:
            await self.long_term.save_knowledge(
                topic=key, content=str(data), source="manual",
            )
        elif storage == "vector" and self.vector:
            await self.vector.store(content=str(data), metadata={"key": key})

    async def search_memory(self, query: str, limit: int = 5) -> list[dict]:
        return await self._search_all(query, limit)

    async def retrieve_context(self, task: str) -> str:
        context = await self.on_new_task(task)
        return self._format_context(context)

    async def delete_memory(self, storage: str, key: str) -> bool:
        if storage == "working":
            if key in self.working.context:
                del self.working.context[key]
                return True
            return False
        elif storage == "vector" and self.vector:
            return await self.vector.delete(key)
        elif storage in ("task", "solution", "preference", "knowledge") and self.long_term:
            return await self.long_term.delete(storage, int(key))
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _search_all(self, query: str, limit: int) -> list[dict]:
        results = []

        if self.long_term:
            for hit in await self.long_term.search_tasks(query, limit=limit):
                hit["type"] = "task"
                results.append(hit)
            for hit in await self.long_term.search_solutions(query, limit=limit):
                hit["type"] = "solution"
                results.append(hit)
            for hit in await self.long_term.search_knowledge(query, limit=limit):
                hit["type"] = "knowledge"
                results.append(hit)

        if self.vector:
            for hit in await self.vector.search(query, limit=limit):
                results.append({
                    "type": "vector",
                    "content": hit.content,
                    "score": round(hit.score, 4),
                    "metadata": hit.metadata,
                })

        results.sort(key=lambda x: x.get("score", 0) if isinstance(x.get("score"), (int, float)) else 0, reverse=True)
        return results[:limit]

    def _format_context(self, context: dict) -> str:
        parts = []
        if context.get("previous_tasks"):
            parts.append("## Previous similar tasks")
            for t in context["previous_tasks"]:
                parts.append(f"- Task: {t.get('task', '')}")
                parts.append(f"  Result: {str(t.get('result', ''))[:200]}")
        if context.get("solutions"):
            parts.append("## Known solutions")
            for s in context["solutions"]:
                parts.append(f"- Problem: {s.get('problem', '')}")
                parts.append(f"  Solution: {str(s.get('solution', ''))[:200]}")
        if context.get("knowledge"):
            parts.append("## Relevant knowledge")
            for k in context["knowledge"]:
                parts.append(f"- {k.get('topic', '')}: {str(k.get('content', ''))[:200]}")
        if context.get("preferences"):
            parts.append("## User preferences")
            for k, v in context["preferences"].items():
                parts.append(f"- {k}: {v}")
        return "\n".join(parts)

    def snapshot(self) -> dict:
        return {
            "working": self.working.snapshot(),
            "vector_entries": self.vector.count() if self.vector else 0,
        }


# ---------------------------------------------------------------------------
# Backward-compatible alias (used by legacy orchestrator)
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    Legacy in-memory key-value store for backward compatibility.
    Replaced by WorkingMemory / LongTermMemory / VectorMemory / MemoryManager.
    """

    def __init__(self):
        self._data: dict[str, dict] = {}

    def save(self, key: str, value: dict) -> None:
        self._data[key] = value

    def get(self, key: str) -> Optional[dict]:
        return self._data.get(key)

    def append(self, key: str, field: str, value: str) -> None:
        if key not in self._data:
            self._data[key] = {}
        if field not in self._data[key]:
            self._data[key][field] = []
        self._data[key][field].append(value)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()
