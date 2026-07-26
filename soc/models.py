"""
SOC domain models.

Data classes for alerts, IOCs, incidents, and threats used across
all SOC agents in the Agent Harness.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------


@dataclass
class Alert:
    """A security alert from a SIEM or detection system."""
    id: str
    title: str
    description: str
    source: str
    severity: str = "Medium"
    mitre_techniques: list[str] = field(default_factory=list)
    kill_chain_stage: str = ""
    indicators: list[str] = field(default_factory=list)
    affected_hosts: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    raw_data: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "severity": self.severity,
            "mitre_techniques": self.mitre_techniques,
            "kill_chain_stage": self.kill_chain_stage,
            "indicators": self.indicators,
            "affected_hosts": self.affected_hosts,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# IOC
# ---------------------------------------------------------------------------


@dataclass
class IOC:
    """Indicator of Compromise."""
    value: str
    ioc_type: str  # ip, domain, hash, url, registry, filepath
    context: str = ""
    confidence: float = 0.5
    source: str = ""
    first_seen: str = ""

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "type": self.ioc_type,
            "context": self.context,
            "confidence": self.confidence,
            "source": self.source,
            "first_seen": self.first_seen,
        }


IOC_TYPES = ["ip", "domain", "hash", "url", "registry", "filepath", "email", "mutex"]


# ---------------------------------------------------------------------------
# Log Entry
# ---------------------------------------------------------------------------


@dataclass
class LogEntry:
    """A single log line with parsed metadata."""
    raw: str
    timestamp: str = ""
    source_ip: str = ""
    dest_ip: str = ""
    source_port: int = 0
    dest_port: int = 0
    protocol: str = ""
    action: str = ""
    user: str = ""
    hostname: str = ""
    log_source: str = ""
    event_id: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source_ip": self.source_ip,
            "dest_ip": self.dest_ip,
            "source_port": self.source_port,
            "dest_port": self.dest_port,
            "protocol": self.protocol,
            "action": self.action,
            "user": self.user,
            "hostname": self.hostname,
            "log_source": self.log_source,
            "event_id": self.event_id,
        }


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A finding from analysis — used by all SOC agents."""
    title: str
    description: str
    severity: str = "Medium"
    mitre_technique: str = ""
    affected_entities: list[str] = field(default_factory=list)
    recommendation: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "mitre_technique": self.mitre_technique,
            "affected_entities": self.affected_entities,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Incident
# ---------------------------------------------------------------------------


@dataclass
class Incident:
    """A security incident under investigation."""
    id: str
    title: str
    description: str
    severity: str = "Medium"
    status: str = "Open"
    alerts: list[Alert] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    affected_systems: list[str] = field(default_factory=list)
    iocs: list[IOC] = field(default_factory=list)
    timeline: list[str] = field(default_factory=list)
    containment_actions: list[str] = field(default_factory=list)
    remediation_plan: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "alerts": [a.to_dict() for a in self.alerts],
            "findings": [f.to_dict() for f in self.findings],
            "affected_systems": self.affected_systems,
            "iocs": [i.to_dict() for i in self.iocs],
            "timeline": self.timeline,
            "containment_actions": self.containment_actions,
            "remediation_plan": self.remediation_plan,
            "created_at": self.created_at,
        }
