"""CLI: import manually written CTF knowledge into the agent memory stores.

Usage:
    python scripts/import_manual_knowledge.py

Reads knowledge/imported/manual_record.txt, parses each challenge record,
and stores it through the existing SolutionMemory and StrategyMemory.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.importer.manual_loader import import_manual_knowledge


def main() -> int:
    report = import_manual_knowledge(imported_by="Jason")

    print("Imported:")
    print(f"- {report['imported']} challenges")
    print()
    print("Skipped:")
    print(f"- {report['skipped']}")
    print()
    print("Duplicates:")
    print(f"- {report['duplicates']}")
    print()
    print("Errors:")
    print(f"- {report['errors']}")

    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
