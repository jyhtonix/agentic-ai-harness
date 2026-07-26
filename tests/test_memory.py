"""
Tests for the three-tier memory system.

Test coverage:
  WorkingMemory  — ephemeral in-memory session storage
  VectorMemory   — semantic search with numpy cosine similarity
  MemoryManager  — facade using mocked long-term and vector stores
  LongTermMemory — PostgreSQL-backed store (requires aiosqlite)
"""

import pytest

from core.memory import (
    WorkingMemory,
    VectorMemory,
    VectorEntry,
    MemoryManager,
    LongTermMemory,
)
from models.embeddings import Embedder


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class FakeEmbedder(Embedder):
    """Returns deterministic embeddings (one-hot-like vectors)."""

    def __init__(self, dimension: int = 4):
        self.dimension = dimension
        self.calls = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        # Simple hash-based embedding for deterministic tests
        h = hash(text) & 0xFFFFFFFF
        vec = [float((h >> (i * 4)) & 0xF) / 15.0 for i in range(self.dimension)]
        return vec


class FakeEmbedderFixed(FakeEmbedder):
    """Returns the same vector for every input."""

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0, 0.0, 0.0]


class StubLongTerm:
    """In-memory stub that matches LongTermMemory's interface."""

    def __init__(self):
        self.tasks = []
        self.solutions = []
        self.preferences = {}
        self.knowledge = []

    async def save_task(self, task, result="", success=True, metadata=None):
        self.tasks.append(dict(task=task, result=result, success=success))
        return len(self.tasks)

    async def search_tasks(self, query, limit=10):
        return [t for t in self.tasks if query.lower() in t["task"].lower()][:limit]

    async def get_task(self, task_id):
        if 0 < task_id <= len(self.tasks):
            return self.tasks[task_id - 1]
        return None

    async def save_solution(self, problem, solution, patterns=None, rating=1.0):
        self.solutions.append(dict(problem=problem, solution=solution, patterns=patterns))
        return len(self.solutions)

    async def search_solutions(self, query, limit=10):
        return [s for s in self.solutions if query.lower() in s["problem"].lower()][:limit]

    async def set_preference(self, user_id, key, value):
        self.preferences[(user_id, key)] = value

    async def get_preference(self, user_id, key):
        return self.preferences.get((user_id, key))

    async def get_all_preferences(self, user_id):
        return {k: v for (uid, k), v in self.preferences.items() if uid == user_id}

    async def save_knowledge(self, topic, content, source="", tags=None):
        self.knowledge.append(dict(topic=topic, content=content, source=source, tags=tags))
        return len(self.knowledge)

    async def search_knowledge(self, query, limit=10):
        return [k for k in self.knowledge if query.lower() in k["topic"].lower()][:limit]

    async def delete(self, table, record_id):
        store = {"task": self.tasks, "solution": self.solutions, "knowledge": self.knowledge}
        lst = store.get(table, [])
        if 0 < record_id <= len(lst):
            lst.pop(record_id - 1)
            return True
        return False


# ---------------------------------------------------------------------------
# WorkingMemory
# ---------------------------------------------------------------------------


class TestWorkingMemory:
    def test_set_and_get_task(self):
        wm = WorkingMemory()
        wm.set_task("build feature X")
        assert wm.get_task() == "build feature X"

    def test_set_task_with_goal(self):
        wm = WorkingMemory()
        wm.set_task("refactor", "improve performance")
        assert wm.goal == "improve performance"

    def test_add_message(self):
        wm = WorkingMemory()
        wm.add_message("user", "hello")
        wm.add_message("assistant", "hi")
        assert len(wm.conversation) == 2
        assert wm.conversation[0]["role"] == "user"
        assert wm.conversation[0]["content"] == "hello"

    def test_get_history_limit(self):
        wm = WorkingMemory()
        for i in range(5):
            wm.add_message("user", str(i))
        assert len(wm.get_history(3)) == 3

    def test_get_history_all(self):
        wm = WorkingMemory()
        for i in range(5):
            wm.add_message("user", str(i))
        assert len(wm.get_history()) == 5

    def test_context_get_set(self):
        wm = WorkingMemory()
        wm.set_context("key1", {"nested": True})
        assert wm.get_context("key1") == {"nested": True}
        assert wm.get_context("missing", "default") == "default"

    def test_clear(self):
        wm = WorkingMemory()
        wm.set_task("task")
        wm.add_message("user", "msg")
        wm.set_context("k", "v")
        wm.clear()
        assert wm.get_task() == ""
        assert wm.conversation == []
        assert wm.context == {}

    def test_snapshot(self):
        wm = WorkingMemory()
        wm.set_task("test", "goal")
        snap = wm.snapshot()
        assert snap["current_task"] == "test"
        assert snap["goal"] == "goal"
        assert "elapsed" in snap


# ---------------------------------------------------------------------------
# VectorMemory
# ---------------------------------------------------------------------------


class TestVectorMemory:
    @pytest.mark.asyncio
    async def test_store_and_count(self):
        vm = VectorMemory(FakeEmbedder())
        eid = await vm.store("hello world")
        assert eid == "vec_0"
        assert vm.count() == 1

    @pytest.mark.asyncio
    async def test_search_finds_similar(self):
        vm = VectorMemory(FakeEmbedderFixed())

        await vm.store("apple fruit")
        await vm.store("orange fruit")
        await vm.store("rocket ship")

        results = await vm.search("fruit", limit=5)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_returns_scored_results(self):
        vm = VectorMemory(FakeEmbedderFixed())
        await vm.store("something")
        results = await vm.search("something", limit=5)
        assert len(results) == 1
        assert results[0].score >= 0

    @pytest.mark.asyncio
    async def test_empty_search(self):
        vm = VectorMemory(FakeEmbedder())
        results = await vm.search("nothing")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_by_vector(self):
        vm = VectorMemory(FakeEmbedder())
        await vm.store("item")
        vec = [0.5, 0.5, 0.5, 0.5]
        results = await vm.search_by_vector(vec)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_delete(self):
        vm = VectorMemory(FakeEmbedder())
        eid = await vm.store("delete me")
        assert vm.count() == 1
        assert await vm.delete(eid) is True
        assert vm.count() == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        vm = VectorMemory(FakeEmbedder())
        assert await vm.delete("nonexistent") is False

    @pytest.mark.asyncio
    async def test_clear(self):
        vm = VectorMemory(FakeEmbedder())
        await vm.store("a")
        await vm.store("b")
        await vm.clear()
        assert vm.count() == 0

    @pytest.mark.asyncio
    async def test_store_with_explicit_embedding(self):
        vm = VectorMemory(FakeEmbedder())
        eid = await vm.store("explicit", embedding=[1.0, 0.0, 0.0, 0.0])
        assert eid == "vec_0"
        assert vm._entries[0].embedding == [1.0, 0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------


class TestMemoryManager:
    @pytest.mark.asyncio
    async def test_on_new_task_sets_working_memory(self):
        mm = MemoryManager()
        await mm.on_new_task("build feature")
        assert mm.working.get_task() == "build feature"

    @pytest.mark.asyncio
    async def test_on_new_task_searches_and_loads_context(self):
        lt = StubLongTerm()
        await lt.save_knowledge("python patterns", "use decorators for logging")
        vm = VectorMemory(FakeEmbedderFixed())

        mm = MemoryManager(working=WorkingMemory(), long_term=lt, vector=vm)
        context = await mm.on_new_task("python patterns")

        assert len(context["knowledge"]) >= 1
        assert "python patterns" in context["knowledge"][0].get("topic", "")
        context_str = mm.working.get_context("retrieved_context")
        assert context_str is not None
        assert "use decorators" in context_str

    @pytest.mark.asyncio
    async def test_on_new_task_includes_preferences(self):
        lt = StubLongTerm()
        await lt.set_preference("user1", "language", "python")

        mm = MemoryManager(working=WorkingMemory(), long_term=lt)
        context = await mm.on_new_task("write code", user_id="user1")

        assert context["preferences"].get("language") == "python"

    @pytest.mark.asyncio
    async def test_on_task_complete_saves_all_stores(self):
        lt = StubLongTerm()
        vm = VectorMemory(FakeEmbedderFixed())

        mm = MemoryManager(working=WorkingMemory(), long_term=lt, vector=vm)
        await mm.on_task_complete(
            task="add logging",
            result="added decorators",
            success=True,
            patterns=["decorator", "logging"],
        )

        assert len(lt.tasks) == 1
        assert lt.tasks[0]["task"] == "add logging"
        assert lt.tasks[0]["success"] is True

        assert len(lt.solutions) == 1
        assert lt.solutions[0]["problem"] == "add logging"

        assert len(lt.knowledge) == 1
        assert lt.knowledge[0]["topic"] == "add logging"

        assert vm.count() == 1

    @pytest.mark.asyncio
    async def test_on_task_complete_only_saves_on_success(self):
        lt = StubLongTerm()
        vm = VectorMemory(FakeEmbedderFixed())

        mm = MemoryManager(working=WorkingMemory(), long_term=lt, vector=vm)
        await mm.on_task_complete(
            task="failed task", result="", success=False,
        )

        assert len(lt.tasks) == 1
        assert lt.tasks[0]["success"] is False
        assert len(lt.solutions) == 0
        assert len(lt.knowledge) == 0
        assert vm.count() == 0

    @pytest.mark.asyncio
    async def test_search_memory_aggregates_results(self):
        lt = StubLongTerm()
        await lt.save_task("search this task", result="done")
        await lt.save_solution("search this problem", "solution text")
        await lt.save_knowledge("search this topic", "knowledge content")

        mm = MemoryManager(working=WorkingMemory(), long_term=lt)
        results = await mm.search_memory("search this", limit=10)

        assert any(r.get("type") == "task" for r in results)
        assert any(r.get("type") == "solution" for r in results)
        assert any(r.get("type") == "knowledge" for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_context_returns_formatted_string(self):
        lt = StubLongTerm()
        await lt.save_knowledge("caching", "use redis for caching")

        mm = MemoryManager(working=WorkingMemory(), long_term=lt)
        ctx = await mm.retrieve_context("caching")

        assert isinstance(ctx, str)
        assert "caching" in ctx
        assert "redis" in ctx

    @pytest.mark.asyncio
    async def test_save_memory_working(self):
        mm = MemoryManager()
        await mm.save_memory("working", "temp_key", {"value": 42})
        assert mm.working.get_context("temp_key") == {"value": 42}

    @pytest.mark.asyncio
    async def test_save_memory_preference(self):
        lt = StubLongTerm()
        mm = MemoryManager(working=WorkingMemory(), long_term=lt)
        await mm.save_memory("preference", "language", {
            "user_id": "user1",
            "value": "python",
        })
        assert await lt.get_preference("user1", "language") == "python"

    @pytest.mark.asyncio
    async def test_save_memory_knowledge(self):
        lt = StubLongTerm()
        mm = MemoryManager(working=WorkingMemory(), long_term=lt)
        await mm.save_memory("knowledge", "some topic", "some content")
        results = await lt.search_knowledge("some topic")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_save_memory_vector(self):
        vm = VectorMemory(FakeEmbedderFixed())
        mm = MemoryManager(working=WorkingMemory(), vector=vm)
        await mm.save_memory("vector", "mykey", "vector content")
        assert vm.count() == 1

    @pytest.mark.asyncio
    async def test_delete_memory_working(self):
        mm = MemoryManager()
        mm.working.set_context("key", "value")
        assert await mm.delete_memory("working", "key") is True
        assert mm.working.get_context("key") is None

    @pytest.mark.asyncio
    async def test_delete_memory_working_missing(self):
        mm = MemoryManager()
        assert await mm.delete_memory("working", "nonexistent") is False

    @pytest.mark.asyncio
    async def test_delete_memory_vector(self):
        vm = VectorMemory(FakeEmbedderFixed())
        eid = await vm.store("content")
        mm = MemoryManager(working=WorkingMemory(), vector=vm)
        assert await mm.delete_memory("vector", eid) is True
        assert vm.count() == 0

    @pytest.mark.asyncio
    async def test_delete_memory_long_term(self):
        lt = StubLongTerm()
        tid = await lt.save_task("task to delete")
        mm = MemoryManager(working=WorkingMemory(), long_term=lt)
        assert await mm.delete_memory("task", str(tid)) is True
        assert await lt.get_task(tid) is None

    @pytest.mark.asyncio
    async def test_delete_memory_long_term_invalid_table(self):
        lt = StubLongTerm()
        mm = MemoryManager(working=WorkingMemory(), long_term=lt)
        assert await mm.delete_memory("invalid", "1") is False

    @pytest.mark.asyncio
    async def test_snapshot(self):
        mm = MemoryManager()
        await mm.on_new_task("snapshot test")
        snap = mm.snapshot()
        assert snap["working"]["current_task"] == "snapshot test"
        assert "vector_entries" in snap

    @pytest.mark.asyncio
    async def test_search_ranks_vector_highest(self):
        lt = StubLongTerm()
        await lt.save_task("exact task match", result="done")
        vm = VectorMemory(FakeEmbedderFixed())
        await vm.store("vector content", metadata={"type": "vector_test"})

        mm = MemoryManager(working=WorkingMemory(), long_term=lt, vector=vm)
        results = await mm.search_memory("anything", limit=10)

        assert len(results) >= 1


# ---------------------------------------------------------------------------
# LongTermMemory (integration — requires aiosqlite)
# ---------------------------------------------------------------------------

pytest.importorskip("aiosqlite", reason="aiosqlite not installed, skipping DB tests")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.connection import Base


async def _make_factory():
    """Create an in-memory SQLite engine, create all tables, and return
    an async_sessionmaker bound to it. The caller must dispose the engine."""
    import database.models  # ensure models are registered on Base.metadata
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


@pytest.mark.asyncio
async def test_ltm_save_and_search_tasks():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        tid = await ltm.save_task("implement login", result="added OAuth", success=True)
        assert tid > 0
        results = await ltm.search_tasks("login")
        assert len(results) >= 1
        assert results[0]["task"] == "implement login"
        assert results[0]["result"] == "added OAuth"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ltm_get_task():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        tid = await ltm.save_task("task A", result="done")
        record = await ltm.get_task(tid)
        assert record is not None
        assert record["task"] == "task A"
        assert record["result"] == "done"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ltm_get_task_missing():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        assert await ltm.get_task(999) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ltm_save_and_search_solutions():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        sid = await ltm.save_solution(
            "slow queries",
            "add indexes",
            patterns=["index", "optimization"],
            rating=0.95,
        )
        assert sid > 0
        results = await ltm.search_solutions("slow")
        assert len(results) >= 1
        assert "index" in results[0]["patterns"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ltm_preferences():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        await ltm.set_preference("user1", "language", "python")
        await ltm.set_preference("user1", "theme", "dark")
        assert await ltm.get_preference("user1", "language") == "python"
        assert await ltm.get_preference("user1", "theme") == "dark"
        prefs = await ltm.get_all_preferences("user1")
        assert prefs == {"language": "python", "theme": "dark"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ltm_preference_update():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        await ltm.set_preference("user1", "language", "python")
        await ltm.set_preference("user1", "language", "rust")
        assert await ltm.get_preference("user1", "language") == "rust"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ltm_save_and_search_knowledge():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        kid = await ltm.save_knowledge(
            "caching strategies",
            "use redis for distributed caching",
            source="docs",
            tags=["cache", "redis", "performance"],
        )
        assert kid > 0
        results = await ltm.search_knowledge("caching")
        assert len(results) >= 1
        assert "redis" in results[0]["content"]
        assert "redis" in results[0]["tags"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ltm_delete():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        tid = await ltm.save_task("to delete")
        assert await ltm.delete("task", tid) is True
        assert await ltm.get_task(tid) is None
        assert await ltm.delete("task", tid) is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_ltm_delete_invalid_table():
    engine, factory = await _make_factory()
    try:
        ltm = LongTermMemory(factory)
        assert await ltm.delete("invalid_table", 1) is False
    finally:
        await engine.dispose()
