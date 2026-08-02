"""CLI: capture a solved CTF challenge into agent memory.

The entry point for solves that happened OUTSIDE the harness pipeline
(e.g. a standalone exploit script, an ad-hoc socket session, or a manual
write-up). Reads a structured summary (JSON) and persists it through the
Experience Capture seam into the same SolutionMemory / StrategyMemory stores
that the supervisor path uses.

Usage:
    python scripts/capture_external_solve.py summary.json
    python scripts/capture_external_solve.py summary.json --source exploit-script

Summary JSON schema (all optional except challenge_id + category):
    {
        "challenge_id": "Echo Escape 2",
        "category": "pwn",
        "difficulty": "medium",
        "description": "32-bit non-PIE, fgets overflow",
        "approach": "overflow 44 bytes to win() at 0x08049276",
        "tools_used": ["python3", "pwntools", "nc"],
        "agents_used": ["manual_capture"],
        "successful_techniques": ["ret2win", "offset-cycle"],
        "failed_approaches": ["offset 36"],
        "final_solution_reasoning": "...",
        "flag_result": "picoCTF{...}",
        "confidence": 0.9,
        "source": "external_script",
        "imported_by": "Jason"
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.capture.experience_capture import capture_solve
from knowledge.capture.solve_summary import CaptureSummary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary_file", type=Path, help="Path to the summary JSON")
    parser.add_argument("--source", default=None, help="Override provenance source")
    parser.add_argument("--imported-by", default=None, help="Override who imported")
    args = parser.parse_args(argv)

    if not args.summary_file.exists():
        print(f"ERROR: summary file not found: {args.summary_file}", file=sys.stderr)
        return 1

    with open(args.summary_file, encoding="utf-8-sig") as f:
        data = json.load(f)
    summary = CaptureSummary.from_dict(data)

    report = capture_solve(
        summary,
        source=args.source,
        imported_by=args.imported_by,
    )

    if report["status"] == "duplicate":
        print(f"Duplicate: '{report['challenge_id']}' already in memory.")
        return 0

    print(f"Imported '{report['challenge_id']}' [{report['category']}] "
          f"source={summary.source} into memory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
