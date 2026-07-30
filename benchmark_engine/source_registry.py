"""External CTF source tracking and metadata registry."""

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("benchmark_engine.source_registry")

BUILTIN_SOURCES = {
    "educational_ctf": {
        "name": "Educational CTF Collection",
        "type": "educational",
        "license": "educational",
        "url": "",
        "description": "Curated educational CTF challenges for benchmarking",
    },
    "picoctf": {
        "name": "picoCTF",
        "type": "competition",
        "license": "educational",
        "url": "https://picoctf.org",
        "description": "Carnegie Mellon's CTF competition challenges",
    },
    "cryptohack": {
        "name": "CryptoHack",
        "type": "educational",
        "license": "educational",
        "url": "https://cryptohack.org",
        "description": "Cryptography-focused CTF challenges",
    },
    "hackthebox": {
        "name": "Hack The Box",
        "type": "platform",
        "license": "commercial",
        "url": "https://hackthebox.com",
        "description": "HTB CTF challenges and machines",
    },
    "tryhackme": {
        "name": "TryHackMe",
        "type": "educational",
        "license": "commercial",
        "url": "https://tryhackme.com",
        "description": "THM guided CTF learning paths",
    },
    "rootme": {
        "name": "Root-Me",
        "type": "platform",
        "license": "educational",
        "url": "https://root-me.org",
        "description": "French CTF platform with diverse challenges",
    },
}


class CTFSourceRegistry:
    def __init__(self, sources_file: Optional[str] = None):
        self._sources: dict[str, dict] = dict(BUILTIN_SOURCES)
        self._sources_file = sources_file
        if sources_file:
            self._load(sources_file)

    def register(self, source_id: str, metadata: dict) -> None:
        self._sources[source_id] = metadata
        logger.info("Registered CTF source: %s (%s)", source_id, metadata.get("name", ""))

    def get(self, source_id: str) -> Optional[dict]:
        return self._sources.get(source_id)

    def list_sources(self) -> dict[str, str]:
        return {sid: meta.get("name", sid) for sid, meta in self._sources.items()}

    def get_by_type(self, source_type: str) -> dict[str, dict]:
        return {sid: meta for sid, meta in self._sources.items() if meta.get("type") == source_type}

    def _load(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            logger.warning("Sources file not found: %s", path)
            return
        try:
            with open(p) as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                for sid, meta in data.get("sources", {}).items():
                    self._sources[sid] = meta
        except (yaml.YAMLError, OSError) as e:
            logger.warning("Cannot load sources: %s", e)

    def __contains__(self, source_id: str) -> bool:
        return source_id in self._sources

    def __len__(self) -> int:
        return len(self._sources)
