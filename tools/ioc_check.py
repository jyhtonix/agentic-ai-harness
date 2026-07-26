"""
IOC Check Tool.

Parses, validates, and categorises Indicators of Compromise (IOCs).
Supports IP addresses, domains, URLs, file hashes (MD5/SHA1/SHA256),
registry paths, file paths, and mutex names.

Usage:
    tool = IOCCheckTool()
    result = await tool.execute(text="Suspicious IP 192.168.1.50 and hash d41d8cd98f00b204e9800998ecf8427e")
    # Returns parsed IOC objects with types and validation status
"""

import logging
import re
from typing import Optional

from tools.base import BaseTool

logger = logging.getLogger("tools.ioc_check")

# Patterns
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOMAIN_PATTERN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
URL_PATTERN = re.compile(r"https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/\S*)?")
MD5_PATTERN = re.compile(r"\b[a-fA-F0-9]{32}\b")
SHA1_PATTERN = re.compile(r"\b[a-fA-F0-9]{40}\b")
SHA256_PATTERN = re.compile(r"\b[a-fA-F0-9]{64}\b")
FILEPATH_PATTERN = re.compile(r"(?:[a-zA-Z]:)?(?:/|\\)(?:[\w\s.-]+(?:/|\\))+[\w\s.-]+\.[a-zA-Z]{2,}")
REGISTRY_PATTERN = re.compile(r"(?:HKEY|HKLM|HKCU|HKCR|HKU)[\\/][A-Za-z0-9_\\/]+")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
MUTEX_PATTERN = re.compile(r"\b(?:Global\\|Local\\)?[A-Za-z0-9_]+(?:Mutex|mutex)\b")

PRIVATE_RANGES = [
    ("10.0.0.0", "10.255.255.255"),
    ("172.16.0.0", "172.31.255.255"),
    ("192.168.0.0", "192.168.255.255"),
    ("127.0.0.0", "127.255.255.255"),
]


def _ip_to_int(ip: str) -> int:
    parts = [int(x) for x in ip.split(".")]
    return (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]


def _is_private_ip(ip: str) -> bool:
    try:
        ip_int = _ip_to_int(ip)
        for start, end in PRIVATE_RANGES:
            if _ip_to_int(start) <= ip_int <= _ip_to_int(end):
                return True
    except Exception:
        pass
    return False


def validate_hash(h: str) -> Optional[str]:
    h = h.strip()
    if MD5_PATTERN.fullmatch(h):
        return "md5"
    if SHA1_PATTERN.fullmatch(h):
        return "sha1"
    if SHA256_PATTERN.fullmatch(h):
        return "sha256"
    return None


class IOCCheckTool(BaseTool):
    """
    Parses raw text and extracts indicators of compromise.
    Returns a structured list of IOCs with type, value, and context.
    """

    name = "ioc_check"
    description = "Parse text and extract indicators of compromise (IPs, domains, hashes, URLs, file paths, registry keys, emails)"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Raw text to scan for IOCs"},
        },
        "required": ["text"],
    }

    async def execute(self, text: str = "", **kwargs) -> str:
        text = kwargs.get("text", text)
        if not text:
            return "No text provided."

        iocs = []

        for match in IP_PATTERN.finditer(text):
            ip = match.group()
            iocs.append({
                "type": "ip",
                "value": ip,
                "context": _get_context(text, match.start(), match.end()),
                "private": _is_private_ip(ip),
            })

        for match in SHA256_PATTERN.finditer(text):
            iocs.append({
                "type": "sha256",
                "value": match.group(),
                "context": _get_context(text, match.start(), match.end()),
            })

        for match in SHA1_PATTERN.finditer(text):
            value = match.group()
            if not SHA256_PATTERN.fullmatch(value):
                iocs.append({
                    "type": "sha1",
                    "value": value,
                    "context": _get_context(text, match.start(), match.end()),
                })

        for match in MD5_PATTERN.finditer(text):
            value = match.group()
            if not SHA1_PATTERN.fullmatch(value) and not SHA256_PATTERN.fullmatch(value):
                iocs.append({
                    "type": "md5",
                    "value": value,
                    "context": _get_context(text, match.start(), match.end()),
                })

        for match in URL_PATTERN.finditer(text):
            url = match.group()
            domain_match = DOMAIN_PATTERN.search(url)
            if domain_match and not any(i["value"] == url for i in iocs):
                iocs.append({
                    "type": "url",
                    "value": url,
                    "context": _get_context(text, match.start(), match.end()),
                })

        for match in DOMAIN_PATTERN.finditer(text):
            domain = match.group()
            if not any(i["value"] == domain for i in iocs):
                is_url = any(domain in i["value"] for i in iocs if i["type"] == "url")
                if not is_url:
                    iocs.append({
                        "type": "domain",
                        "value": domain,
                        "context": _get_context(text, match.start(), match.end()),
                    })

        for match in EMAIL_PATTERN.finditer(text):
            iocs.append({
                "type": "email",
                "value": match.group(),
                "context": _get_context(text, match.start(), match.end()),
            })

        for match in FILEPATH_PATTERN.finditer(text):
            iocs.append({
                "type": "filepath",
                "value": match.group(),
                "context": _get_context(text, match.start(), match.end()),
            })

        for match in REGISTRY_PATTERN.finditer(text):
            iocs.append({
                "type": "registry",
                "value": match.group(),
                "context": _get_context(text, match.start(), match.end()),
            })

        for match in MUTEX_PATTERN.finditer(text):
            iocs.append({
                "type": "mutex",
                "value": match.group(),
                "context": _get_context(text, match.start(), match.end()),
            })

        summary = "\n".join(
            f"[{i['type']:>8}] {i['value']}" + (" (private)" if i.get("private") else "")
            for i in iocs
        ) if iocs else "No IOCs found."

        return f"Found {len(iocs)} IOC(s):\n{summary}"


def _get_context(text: str, start: int, end: int, window: int = 30) -> str:
    """Extract surrounding context for a match."""
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)
    prefix = "..." if ctx_start > 0 else ""
    suffix = "..." if ctx_end < len(text) else ""
    return f"{prefix}{text[ctx_start:ctx_end].strip()}{suffix}"
