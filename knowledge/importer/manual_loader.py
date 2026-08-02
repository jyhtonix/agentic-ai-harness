"""Manual knowledge loader — imports handwritten CTF solution records.

Reads a flat text file of challenge records (separated by lines of `=`),
parses each record into structured fields, converts it to the existing
CTFEpisode/SolutionMemory internal format, and persists it through the
existing memory stores (SolutionMemory + StrategyMemory). No LLM, no new
databases, no changes to agent solving logic.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from memory.solutions import SolutionMemory
from memory.strategies import StrategyMemory

logger = logging.getLogger("knowledge.importer.manual_loader")

DEFAULT_SOURCE_FILE = Path(__file__).resolve().parents[2] / "knowledge" / "imported" / "manual_record.txt"

SEPARATOR_RE = re.compile(r"^=+$")

# Category prefixes that appear as "PREFIX - Challenge Name" titles.
KNOWN_CATEGORY_PREFIXES = [
    "web exploitation", "binary exploitation", "reverse engineering",
    "artificial intelligence", "forensics", "cryptography", "malware",
    "general skills", "general", "crypto", "pwn", "rev", "web", "binary",
]

CATEGORY_MAP = {
    "web exploitation": "web",
    "web": "web",
    "binary exploitation": "pwn",
    "binary": "pwn",
    "pwn": "pwn",
    "reverse engineering": "reverse_engineering",
    "rev": "reverse_engineering",
    "artificial intelligence": "ai",
    "ai": "ai",
    "cryptography": "crypto",
    "crypto": "crypto",
    "forensics": "forensics",
    "malware": "malware",
    "general skills": "general",
    "general": "general",
    "devops": "devops",
}

CONFIDENCE_MAP = {
    "high": 0.9,
    "medium": 0.7,
    "medium-high": 0.8,
    "low": 0.5,
    "unknown": 0.5,
    "n/a": 0.5,
}

# Field labels that delimit sections inside a solution block.
SECTION_HEADERS = re.compile(
    r"^\s*(Category|Difficulty|Tools Used|Evidence|Solution|Reasoning|Flag|"
    r"Confidence|Learning|Successful approach|Failed approach|Future improvement|"
    r"Method|Approach|Hints|Investigation|Challenge Classification)\s*:?",
    re.IGNORECASE,
)

FLAG_RE = re.compile(r"(?:picoCTF|flag|academy)\{[^}\n]+\}", re.IGNORECASE)

TITLE_RE = re.compile(
    r"^\s*(?P<cat>(?:Web Exploitation|Binary Exploitation|Reverse Engineering|"
    r"Artificial Intelligence|Forensics|Cryptography|Malware|General Skills|"
    r"General|Crypto|Pwn|Rev|Web|Binary))\s*-\s*(?P<name>.+?)\s*$",
    re.IGNORECASE,
)


class ManualKnowledgeLoader:
    """Parses manual CTF records and writes them into the memory stores."""

    def __init__(
        self,
        source_file: Optional[Path] = None,
        solution_memory: Optional[SolutionMemory] = None,
        strategy_memory: Optional[StrategyMemory] = None,
        imported_by: str = "Jason",
    ):
        self.source_file = Path(source_file or DEFAULT_SOURCE_FILE)
        self.solution_memory = solution_memory or SolutionMemory()
        self.strategy_memory = strategy_memory or StrategyMemory()
        self.imported_by = imported_by

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_knowledge(self) -> dict:
        """Import all records from the source file.

        Returns a report dict with keys: imported, skipped, duplicates, errors.
        """
        report = {"imported": 0, "skipped": 0, "duplicates": 0, "errors": 0}
        if not self.source_file.exists():
            report["errors"] += 1
            logger.error("Source file not found: %s", self.source_file)
            return report

        records = self._split_records(self.source_file.read_text(encoding="utf-8"))
        seen_names: set[str] = set()

        for idx, record in enumerate(records, 1):
            try:
                fields = self._extract_fields(record)
                name = (fields.get("challenge_name") or "").strip().lower()
                if not name:
                    report["skipped"] += 1
                    logger.warning("Record %d: no challenge name found, skipped", idx)
                    continue

                if self._already_imported(name) or name in seen_names:
                    report["duplicates"] += 1
                    logger.info("Record %d: duplicate of '%s', skipped", idx, fields["challenge_name"])
                    continue

                seen_names.add(name)
                self._store(fields)
                report["imported"] += 1
            except Exception as exc:  # noqa: BLE001 - keep importing the rest
                report["errors"] += 1
                logger.exception("Record %d failed to import: %s", idx, exc)

        return report

    # ------------------------------------------------------------------
    # Splitting / parsing
    # ------------------------------------------------------------------

    def _split_records(self, text: str) -> list[str]:
        """Split the file into records on lines of only '=' characters."""
        segments = re.split(r"^\s*=+\s*$", text, flags=re.MULTILINE)
        # Drop fully empty segments, then merge consecutive prompt+solution
        # pairs so each returned record is one full challenge.
        non_empty = [s for s in segments if s.strip()]
        merged: list[str] = []
        pending_prompt = ""

        for seg in non_empty:
            if self._is_solution_segment(seg):
                merged.append(pending_prompt + "\n" + seg if pending_prompt else seg)
                pending_prompt = ""
            else:
                if pending_prompt:
                    merged.append(pending_prompt)
                pending_prompt = seg

        if pending_prompt:
            merged.append(pending_prompt)
        return merged

    @staticmethod
    def _is_solution_segment(segment: str) -> bool:
        head = segment.strip()[:400]
        markers = [
            "flag recovered", "opencode wins", "flag obtained",
            "challenge solved", "solved. the flag", "category:",
            "confidence:", "successful approach:",
        ]
        return any(m in head.lower() for m in markers)

    def _extract_fields(self, record: str) -> dict:
        """Extract structured fields from one merged challenge record."""
        fields: dict = {}

        title = self._find_title(record)
        if title:
            fields["challenge_name"] = title.group("name").strip()
            fields["category"] = self._map_category(title.group("cat").strip())
        else:
            fields["challenge_name"] = self._fallback_name(record)
            fields["category"] = "general"

        cat_line = self._find_label_value(record, "Category")
        if cat_line and not title:
            fields["category"] = self._map_category(cat_line)

        fields["difficulty"] = self._find_label_value(record, "Difficulty") or "unknown"
        fields["tools_used"] = self._parse_tools(self._find_label_value(record, "Tools Used"))
        if not fields["tools_used"]:
            fields["tools_used"] = self._scan_known_tools(record)
        fields["evidence"] = self._section_after(record, ["Evidence"])
        fields["reasoning"] = self._section_after(record, ["Reasoning"])
        fields["solution"] = self._extract_solution(record)
        fields["lessons_learned"] = self._extract_lessons(record)
        fields["failed_approach"] = self._find_label_value(record, "Failed approach")
        fields["confidence"] = self._parse_confidence(
            self._find_label_value(record, "Confidence")
        )
        flag = FLAG_RE.search(record)
        fields["flag"] = flag.group(0) if flag else None

        if not fields["reasoning"] and fields["solution"]:
            fields["reasoning"] = fields["solution"]
        return fields

    # ------------------------------------------------------------------
    # Field helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_title(text: str) -> Optional[re.Match]:
        for line in text.splitlines():
            m = TITLE_RE.match(line)
            if m:
                return m
        return None

    @staticmethod
    def _fallback_name(record: str) -> str:
        lines = [l.strip() for l in record.splitlines() if l.strip()]
        for line in lines:
            if not line:
                continue
            if line.startswith("@") or line.startswith("./"):
                continue
            low = line.lower()
            if low.startswith("you are") or low.startswith("your task") or low.startswith("connect to"):
                continue
            return line[:60]
        return "unknown_challenge"

    @staticmethod
    def _map_category(raw: str) -> str:
        key = raw.strip().lower()
        return CATEGORY_MAP.get(key, key.replace(" ", "_") or "general")

    @staticmethod
    def _find_label_value(text: str, label: str) -> str:
        pattern = re.compile(
            rf"^\s*{re.escape(label)}\s*:?\s*(.*)$", re.IGNORECASE | re.MULTILINE
        )
        for m in pattern.finditer(text):
            value = m.group(1).strip()
            if value:
                return value
        return ""

    @staticmethod
    def _parse_tools(raw: str) -> list[str]:
        if not raw:
            return []
        tools = [t.strip() for t in re.split(r"[,;]", raw) if t.strip()]
        return tools

    @staticmethod
    def _scan_known_tools(text: str) -> list[str]:
        """Fallback: pick out well-known tool names mentioned in the record."""
        known = [
            "curl", "wget", "python", "python3", "pwntools", "gdb", "cyclic",
            "strings", "file", "binwalk", "exiftool", "volatility", "tshark",
            "tcpdump", "nmap", "nc", "netcat", "john", "hashcat", "sqlmap",
            "sqlite3", "openssl", "steghide", "zsteg", "apktool", "jadx",
            "jadxgui", "objdump", "readelf", "ropper", "one_gadget", "tor",
            "requests", "base64", "rot13",
        ]
        low = text.lower()
        return [t for t in known if re.search(rf"\b{re.escape(t)}\b", low)]

    @staticmethod
    def _parse_confidence(raw: str) -> float:
        key = (raw or "").strip().lower()
        return CONFIDENCE_MAP.get(key, 0.5)

    def _section_after(self, text: str, start_labels: list[str]) -> str:
        """Return the block of text following one of the start labels."""
        lines = text.splitlines()
        start_re = re.compile(
            rf"^\s*({'|'.join(start_labels)})\s*:?\s*$", re.IGNORECASE
        )
        collecting = False
        out: list[str] = []
        for line in lines:
            if collecting:
                if SECTION_HEADERS.match(line):
                    break
                if line.strip():
                    out.append(line.strip())
            elif start_re.match(line):
                collecting = True
        return " ".join(out).strip()

    def _extract_solution(self, text: str) -> str:
        # Solution typically lives under "Solution", "Method", or "Approach".
        for label in ["Solution", "Method", "Approach"]:
            section = self._section_after(text, [label])
            if section:
                return section
        return ""

    def _extract_lessons(self, text: str) -> str:
        parts = []
        for label in ["Successful approach", "Learning", "Future improvement"]:
            section = self._section_after(text, [label])
            if section:
                parts.append(section)
        return " ".join(parts).strip()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _already_imported(self, name: str) -> bool:
        return any(
            (s.get("challenge_id") or "").strip().lower() == name
            for s in self.solution_memory.get_solutions()
        )

    def _store(self, fields: dict) -> None:
        challenge_name = fields["challenge_name"]
        category = fields["category"]
        confidence = fields["confidence"]
        tools = fields["tools_used"]
        techniques = self._to_technique_list(fields["evidence"])
        lessons = self._to_technique_list(fields["lessons_learned"])
        failed = fields["failed_approach"]
        failed_list = [failed] if failed and failed.lower() != "none" else []

        self.solution_memory.record(
            challenge_id=challenge_name,
            category=category,
            difficulty=fields["difficulty"],
            approach=fields["solution"] or challenge_name,
            tools_used=tools,
            agents_used=["manual_import"],
            success=True,
            description=self._find_label_value(
                self._prompt_part(fields), "challenge"
            ) or challenge_name,
            skills_selected=techniques + lessons,
            actions_commands=tools,
            successful_techniques=techniques,
            failed_approaches=failed_list,
            final_solution_reasoning=fields["reasoning"],
            flag_result=fields["flag"],
            confidence=confidence,
            source_metadata={
                "source": "manual_record",
                "filename": self.source_file.name,
                "imported_by": self.imported_by,
                "imported_at": self._now(),
            },
        )

        if fields["solution"]:
            self.strategy_memory.record(
                category,
                f"{challenge_name}: {fields['solution'][:120]}",
                confidence=confidence,
            )
        if failed_list:
            self.strategy_memory.record_failed(category, failed, failure_reason=failed)

    @staticmethod
    def _prompt_part(fields: dict) -> str:
        # Best-effort: not stored separately; description already extracted.
        return ""

    @staticmethod
    def _to_technique_list(text: str) -> list[str]:
        if not text:
            return []
        parts = [p.strip(" -•") for p in text.split(" - ") if p.strip(" -•")]
        return [p for p in parts if len(p) > 2]

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()


def import_manual_knowledge(
    source_file: Optional[Path] = None,
    solution_memory: Optional[SolutionMemory] = None,
    strategy_memory: Optional[StrategyMemory] = None,
    imported_by: str = "Jason",
) -> dict:
    """Convenience wrapper: run the manual knowledge import and return a report."""
    loader = ManualKnowledgeLoader(
        source_file=source_file,
        solution_memory=solution_memory,
        strategy_memory=strategy_memory,
        imported_by=imported_by,
    )
    return loader.import_knowledge()
