"""Tests for the manual knowledge importer (knowledge/importer/manual_loader.py)."""

import json
import tempfile
from pathlib import Path

from memory.solutions import SolutionMemory
from memory.strategies import StrategyMemory
from memory.service import MemoryService
from knowledge.importer.manual_loader import ManualKnowledgeLoader

SOURCE_FILE = Path(__file__).resolve().parents[1] / "knowledge" / "imported" / "manual_record.txt"


def _import_in_temp():
    td = tempfile.TemporaryDirectory()
    sm = SolutionMemory(storage_dir=td.name)
    st = StrategyMemory(storage_dir=td.name)
    loader = ManualKnowledgeLoader(
        source_file=SOURCE_FILE,
        solution_memory=sm,
        strategy_memory=st,
        imported_by="tester",
    )
    return td, sm, st, loader


def test_loader_imports_records():
    td, sm, st, loader = _import_in_temp()
    try:
        report = loader.import_knowledge()
        assert report["errors"] == 0
        assert report["imported"] >= 15
        # The source file itself repeats "Crack the Gate 1", so an in-file
        # duplicate is expected and must be reported (not imported twice).
        assert report["duplicates"] >= 1

        solutions = sm.get_solutions(success=True)
        assert len(solutions) >= 15
        for s in solutions:
            assert s.get("source_metadata", {}).get("source") == "manual_record"
            assert s.get("source_metadata", {}).get("filename") == "manual_record.txt"
            assert s.get("source_metadata", {}).get("imported_by") == "tester"
            assert s.get("category")
            assert s.get("challenge_id")
    finally:
        td.cleanup()


def test_duplicate_import_is_skipped():
    td, sm, st, loader = _import_in_temp()
    try:
        first = loader.import_knowledge()
        second = loader.import_knowledge()
        assert second["imported"] == 0
        assert second["duplicates"] == first["imported"] + first["duplicates"]
        assert len(sm.get_solutions()) == first["imported"]
    finally:
        td.cleanup()


def test_web_techniques_retrievable_via_memory_service():
    td = tempfile.TemporaryDirectory()
    try:
        sm = SolutionMemory(storage_dir=td.name)
        st = StrategyMemory(storage_dir=td.name)
        loader = ManualKnowledgeLoader(
            source_file=SOURCE_FILE,
            solution_memory=sm,
            strategy_memory=st,
            imported_by="tester",
        )
        loader.import_knowledge()

        service = MemoryService(
            solution_memory=sm, strategy_memory=st, memory_dir=td.name
        )
        context = service.format_context("web", query="Web Exploitation", limit=5)
        for keyword in ["session", "cookie", "ssti", "sql", "rot13"]:
            assert keyword in context.lower(), f"expected {keyword!r} in context"
    finally:
        td.cleanup()


def test_import_report_shape():
    td, sm, st, loader = _import_in_temp()
    try:
        report = loader.import_knowledge()
        assert set(report) == {"imported", "skipped", "duplicates", "errors"}
        assert all(isinstance(v, int) for v in report.values())
    finally:
        td.cleanup()


def test_persisted_json_has_source_metadata():
    td = tempfile.TemporaryDirectory()
    try:
        sm = SolutionMemory(storage_dir=td.name)
        st = StrategyMemory(storage_dir=td.name)
        loader = ManualKnowledgeLoader(
            source_file=SOURCE_FILE,
            solution_memory=sm,
            strategy_memory=st,
            imported_by="tester",
        )
        loader.import_knowledge()

        data = json.loads((Path(td.name) / "solutions.json").read_text(encoding="utf-8"))
        assert data, "solutions.json should not be empty"
        for entry in data:
            assert "source_metadata" in entry
    finally:
        td.cleanup()
