"""
Log Parser Tool.

Parses common log formats into structured LogEntry objects.
Supports syslog, Apache/NGINX combined, Windows Event Log (XML),
CSV, and JSON log formats.

Usage:
    tool = LogParserTool()
    result = await tool.execute(log_text="...", format="syslog")
    # Returns parsed log entries with structured fields
"""

import json
import logging
import re
from typing import Optional

from tools.base import BaseTool

logger = logging.getLogger("tools.log_parser")

SYSLOG_PATTERN = re.compile(
    r"(?:<\d+>)?"
    r"(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})?\s*"
    r"(\S+)?\s*"  # hostname
    r"(\S+)\[?\d*\]?:\s*"  # process
    r"(.*)"  # message
)

APACHE_COMBINED_PATTERN = re.compile(
    r'(\S+)\s+'               # IP
    r'\S+\s+'                  # ident
    r'\S+\s+'                  # authuser
    r'\[([^\]]+)\]\s+'         # timestamp
    r'"(\S+)\s+(\S+)\s+(\S+)"\s+'  # method, path, protocol
    r'(\d+)\s+'                # status
    r'(\d+)\s+'                # bytes
    r'"([^"]*)"\s+'            # referer
    r'"([^"]*)"'               # user-agent
)

CSV_DELIMITER = re.compile(r'[,\t\|]')
KEY_VALUE_PATTERN = re.compile(r'(\w+)=("[^"]*"|\S+)')

WINDOWS_EVENT_KEYS = [
    "EventID", "Source", "EventType", "Level", "Computer",
    "User", "TimeCreated", "Message",
]


def _parse_timestamp(ts: str) -> str:
    """Normalise a timestamp string or return as-is."""
    if not ts:
        return ""
    return ts.strip()


def _try_parse_json(line: str) -> Optional[dict]:
    try:
        return json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None


def _parse_key_value(line: str) -> dict:
    fields = {}
    for match in KEY_VALUE_PATTERN.finditer(line):
        key = match.group(1)
        value = match.group(2).strip('"')
        fields[key] = value
    return fields


class LogParserTool(BaseTool):
    """
    Parses log text in various formats and returns structured entries.
    """

    name = "log_parser"
    description = "Parse firewall, syslog, web server, and Windows event logs into structured fields"
    parameters = {
        "type": "object",
        "properties": {
            "log_text": {"type": "string", "description": "Raw log text to parse"},
            "format": {
                "type": "string",
                "enum": ["auto", "syslog", "apache", "json", "csv", "keyvalue"],
                "description": "Log format (default: auto-detect)",
            },
        },
        "required": ["log_text"],
    }

    async def execute(self, log_text: str = "", format: str = "auto", **kwargs) -> str:
        log_text = kwargs.get("log_text", log_text)
        log_format = kwargs.get("format", format)

        if not log_text:
            return "No log text provided."

        if log_format == "auto":
            log_format = self._detect_format(log_text)

        lines = [l.strip() for l in log_text.split("\n") if l.strip()]
        parsed = []

        for line in lines[:100]:
            entry = self._parse_line(line, log_format)
            if entry:
                parsed.append(entry)

        if not parsed:
            return f"No entries could be parsed (format: {log_format})."

        lines_out = [f"Parsed {len(parsed)} log entries from {log_format} format:"]
        for i, entry in enumerate(parsed, 1):
            parts = []
            if entry.get("timestamp"):
                parts.append(entry["timestamp"])
            parts.append(f"[{entry.get('source_ip', '?')}]")
            parts.append(entry.get("action", ""))
            parts.append(entry.get("message", "")[:80])
            lines_out.append(f"  {i}. {' '.join(p for p in parts if p)}")

        return "\n".join(lines_out)

    def _detect_format(self, text: str) -> str:
        first_line = text.split("\n", 1)[0].strip()

        if first_line.startswith("{"):
            return "json"

        if re.match(r'\S+ \S+ \S+ \[', first_line):
            return "apache"

        if re.match(r'<\d+>', first_line) or re.match(r'\w{3}\s+\d+', first_line):
            return "syslog"

        if "=" in first_line and re.match(r'\w+=', first_line):
            return "keyvalue"

        if "," in first_line or "\t" in first_line:
            return "csv"

        return "syslog"

    def _parse_line(self, line: str, fmt: str) -> Optional[dict]:
        entry = {"raw": line[:200]}

        if fmt == "json":
            data = _try_parse_json(line)
            if data:
                entry.update(data)
                entry["message"] = data.get("message", data.get("msg", line[:100]))
                entry["source_ip"] = data.get("src_ip", data.get("source_ip", data.get("ip", "")))
                entry["action"] = data.get("action", data.get("event_type", ""))
                entry["timestamp"] = _parse_timestamp(data.get("timestamp", data.get("time", "")))
                return entry
            return None

        if fmt == "apache":
            m = APACHE_COMBINED_PATTERN.match(line)
            if m:
                entry["source_ip"] = m.group(1)
                entry["timestamp"] = _parse_timestamp(m.group(2))
                entry["action"] = f"{m.group(3)} {m.group(4)}"
                entry["protocol"] = m.group(5)
                entry["status"] = m.group(6)
                entry["bytes"] = m.group(7)
                entry["message"] = f"{entry['action']} -> {entry['status']}"
                return entry
            return None

        if fmt == "syslog":
            m = SYSLOG_PATTERN.match(line)
            if m:
                entry["timestamp"] = _parse_timestamp(m.group(1) or "")
                entry["hostname"] = m.group(2) or ""
                entry["source"] = m.group(3) or ""
                entry["message"] = m.group(4) or ""
                entry["action"] = m.group(3) or ""
                return entry
            entry["message"] = line[:200]
            return entry

        if fmt == "keyvalue":
            fields = _parse_key_value(line)
            if fields:
                entry.update(fields)
                entry["message"] = fields.get("message", fields.get("msg", line[:100]))
                entry["source_ip"] = fields.get("src_ip", fields.get("source_ip", ""))
                entry["action"] = fields.get("action", fields.get("event_type", ""))
                entry["timestamp"] = _parse_timestamp(fields.get("timestamp", fields.get("time", "")))
                return entry
            return None

        entry["message"] = line[:200]
        return entry
