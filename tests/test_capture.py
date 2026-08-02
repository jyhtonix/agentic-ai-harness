"""Tests for the Experience Capture seam (knowledge/capture/).

Verifies that solves performed outside the harness pipeline (external exploit
scripts, manual write-ups) can be recorded into memory through the same
SolutionMemory / StrategyMemory stores the supervisor path uses.
"""

import json
import tempfile
from pathlib import Path

from memory.service import MemoryService
from memory.solutions import SolutionMemory
from memory.strategies import StrategyMemory
from knowledge.capture.experience_capture import capture_solve
from knowledge.capture.solve_summary import CaptureSummary


def _fresh_service():
    td = tempfile.TemporaryDirectory()
    sm = SolutionMemory(storage_dir=td.name)
    st = StrategyMemory(storage_dir=td.name)
    service = MemoryService(solution_memory=sm, strategy_memory=st, memory_dir=td.name)
    return td, service


def test_capture_external_solve_persists_solution():
    td, service = _fresh_service()
    try:
        summary = CaptureSummary(
            challenge_id="Echo Escape 2",
            category="pwn",
            difficulty="medium",
            description="32-bit non-PIE, fgets overflow",
            approach="overflow 44 bytes to win() at 0x08049276",
            tools_used=["python3", "pwntools", "nc"],
            successful_techniques=["ret2win"],
            failed_approaches=["offset 36"],
            final_solution_reasoning="win() at 0x08049276; buf at ebp-0x28; offset 44",
            flag_result="picoCTF{fgets_0v3rfl0w42_9311310a}",
            confidence=0.9,
            source="exploit_script",
            imported_by="tester",
        )
        report = capture_solve(summary, memory_service=service)
        assert report["status"] == "imported"

        solutions = service.solution_memory.get_solutions(success=True)
        assert len(solutions) == 1
        entry = solutions[0]
        assert entry["challenge_id"] == "Echo Escape 2"
        assert entry["category"] == "pwn"
        assert entry["approach"].startswith("overflow 44 bytes")
        assert entry["successful_techniques"] == ["ret2win"]
        assert entry["failed_approaches"] == ["offset 36"]
        assert entry["flag_result"] == "picoCTF{fgets_0v3rfl0w42_9311310a}"
        meta = entry["source_metadata"]
        assert meta["source"] == "exploit_script"
        assert meta["imported_by"] == "tester"
        assert "captured_at" in meta
    finally:
        td.cleanup()


def test_capture_duplicate_is_skipped():
    td, service = _fresh_service()
    try:
        summary = CaptureSummary(
            challenge_id="Echo Escape 2",
            category="pwn",
            approach="overflow 44 bytes to win()",
        )
        first = capture_solve(summary, memory_service=service)
        second = capture_solve(summary, memory_service=service)
        assert first["status"] == "imported"
        assert second["status"] == "duplicate"
        assert len(service.solution_memory.get_solutions()) == 1
    finally:
        td.cleanup()


def test_capture_adds_strategy_and_failed_approach():
    td, service = _fresh_service()
    try:
        summary = CaptureSummary(
            challenge_id="Binary Gauntlet 4",
            category="pwn",
            approach="format string leak then one_gadget",
            failed_approaches=["ret2libc without leak"],
        )
        capture_solve(summary, memory_service=service)
        strategies = service.strategy_memory.get_strategies("pwn")
        assert any("Binary Gauntlet 4" in s for s in strategies)
        failed = service.strategy_memory.get_failed_approaches("pwn")
        assert any("ret2libc" in a for a in failed)
    finally:
        td.cleanup()


def test_capture_retrievable_via_format_context():
    """The exact gap from the audit: an external solve must be retrievable."""
    td, service = _fresh_service()
    try:
        summary = CaptureSummary(
            challenge_id="Echo Escape 2",
            category="pwn",
            difficulty="medium",
            description="32-bit non-PIE binary, fgets buffer overflow",
            approach="send 44 bytes of padding then win() at 0x08049276",
            tools_used=["python3", "pwntools"],
            successful_techniques=["ret2win", "offset-cycle"],
            final_solution_reasoning="win() at 0x08049276; buf at ebp-0x28; offset 44",
        )
        capture_solve(summary, memory_service=service)

        context = service.format_context("pwn", query="buffer overflow read the flag", limit=5)
        assert "Echo Escape 2" in context
        assert "ret2win" in context
        assert "44" in context
    finally:
        td.cleanup()


def test_from_dict_builds_summary():
    data = {
        "challenge_id": "X",
        "category": "crypto",
        "approach": "xortool",
        "tools_used": ["xortool"],
        "unknown_extra_key": "ignored",
    }
    summary = CaptureSummary.from_dict(data)
    assert summary.challenge_id == "X"
    assert summary.category == "crypto"
    assert summary.tools_used == ["xortool"]
    assert not hasattr(summary, "unknown_extra_key")


def test_persisted_json_has_source_metadata():
    td = tempfile.TemporaryDirectory()
    try:
        sm = SolutionMemory(storage_dir=td.name)
        st = StrategyMemory(storage_dir=td.name)
        service = MemoryService(solution_memory=sm, strategy_memory=st, memory_dir=td.name)
        capture_solve(
            CaptureSummary(
                challenge_id="Buffer Gate 7",
                category="pwn",
                approach="ret2win offset 44",
                source="manual_record",
                source_filename="manual_record.txt",
            ),
            memory_service=service,
        )
        data = json.loads((Path(td.name) / "solutions.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["source_metadata"]["source"] == "manual_record"
        assert data[0]["source_metadata"]["filename"] == "manual_record.txt"
    finally:
        td.cleanup()
