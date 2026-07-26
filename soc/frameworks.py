"""
SOC frameworks reference data.

Contains structured representations of:
  - MITRE ATT&CK (common enterprise techniques)
  - NIST Cybersecurity Framework (CSF) functions
  - Cyber Kill Chain stages

Used by SOC agents for mapping, scoring, and reporting.
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# MITRE ATT&CK
# ---------------------------------------------------------------------------

@dataclass
class AttackTechnique:
    id: str
    name: str
    tactic: str
    description: str
    platforms: list[str] = field(default_factory=list)


ENTERPRISE_TECHNIQUES: list[AttackTechnique] = [
    AttackTechnique("T1078", "Valid Accounts", "TA0001-Initial Access",
        "Adversaries may obtain and abuse credentials of existing accounts."),
    AttackTechnique("T1566", "Phishing", "TA0001-Initial Access",
        "Adversaries may send phishing messages to gain access."),
    AttackTechnique("T1190", "Exploit Public-Facing Application", "TA0001-Initial Access",
        "Adversaries may exploit a vulnerability in an internet-facing system."),
    AttackTechnique("T1133", "External Remote Services", "TA0001-Initial Access",
        "Adversaries may use external remote services for initial access."),

    AttackTechnique("T1059", "Command and Scripting Interpreter", "TA0002-Execution",
        "Adversaries may abuse command interpreters to execute commands."),
    AttackTechnique("T1204", "User Execution", "TA0002-Execution",
        "Adversaries may rely on user action to execute malicious payloads."),

    AttackTechnique("T1071", "Application Layer Protocol", "TA0011-Command and Control",
        "Adversaries may use application-layer protocols for C2."),
    AttackTechnique("T1573", "Encrypted Channel", "TA0011-Command and Control",
        "Adversaries may use encryption to conceal C2 traffic."),
    AttackTechnique("T1095", "Non-Application Layer Protocol", "TA0011-Command and Control",
        "Adversaries may use non-application layer protocols for C2."),

    AttackTechnique("T1046", "Network Service Discovery", "TA0007-Discovery",
        "Adversaries may scan for network services."),
    AttackTechnique("T1082", "System Information Discovery", "TA0007-Discovery",
        "Adversaries may gather system information."),

    AttackTechnique("T1053", "Scheduled Task/Job", "TA0003-Persistence",
        "Adversaries may use scheduled tasks for persistence."),
    AttackTechnique("T1547", "Boot or Logon Autostart Execution", "TA0003-Persistence",
        "Adversaries may configure autostart mechanisms."),

    AttackTechnique("T1562", "Impair Defenses", "TA0005-Defense Evasion",
        "Adversaries may disable or impair security tools."),
    AttackTechnique("T1070", "Indicator Removal", "TA0005-Defense Evasion",
        "Adversaries may delete logs and artifacts."),

    AttackTechnique("T1003", "OS Credential Dumping", "TA0006-Credential Access",
        "Adversaries may dump credentials from the OS."),
    AttackTechnique("T1110", "Brute Force", "TA0006-Credential Access",
        "Adversaries may use brute force to gain credentials."),

    AttackTechnique("T1021", "Remote Services", "TA0008-Lateral Movement",
        "Adversaries may use valid accounts to log into remote services."),
    AttackTechnique("T1570", "Lateral Tool Transfer", "TA0008-Lateral Movement",
        "Adversaries may transfer tools between systems."),

    AttackTechnique("T1485", "Data Destruction", "TA0040-Impact",
        "Adversaries may destroy data to disrupt availability."),
    AttackTechnique("T1490", "Inhibit System Recovery", "TA0040-Impact",
        "Adversaries may delete backups and recovery options."),
    AttackTechnique("T1486", "Data Encrypted for Impact", "TA0040-Impact",
        "Adversaries may encrypt data to demand ransom."),

    AttackTechnique("T1048", "Exfiltration Over Alternative Protocol", "TA0010-Exfiltration",
        "Adversaries may exfiltrate data over a different protocol."),
    AttackTechnique("T1020", "Automated Exfiltration", "TA0010-Exfiltration",
        "Adversaries may exfiltrate data automatically."),
]

TACTIC_MAP: dict[str, str] = {
    "TA0001": "Initial Access",
    "TA0002": "Execution",
    "TA0003": "Persistence",
    "TA0004": "Privilege Escalation",
    "TA0005": "Defense Evasion",
    "TA0006": "Credential Access",
    "TA0007": "Discovery",
    "TA0008": "Lateral Movement",
    "TA0009": "Collection",
    "TA0010": "Exfiltration",
    "TA0011": "Command and Control",
    "TA0040": "Impact",
}


def lookup_technique(technique_id: str) -> Optional[AttackTechnique]:
    for t in ENTERPRISE_TECHNIQUES:
        if t.id.upper() == technique_id.upper():
            return t
    return None


def search_techniques(query: str) -> list[AttackTechnique]:
    q = query.lower()
    return [
        t for t in ENTERPRISE_TECHNIQUES
        if q in t.name.lower() or q in t.tactic.lower() or q in t.description.lower()
    ]


# ---------------------------------------------------------------------------
# Cyber Kill Chain
# ---------------------------------------------------------------------------

KILL_CHAIN_STAGES: list[str] = [
    "Reconnaissance",
    "Weaponization",
    "Delivery",
    "Exploitation",
    "Installation",
    "Command and Control",
    "Actions on Objectives",
]


# ---------------------------------------------------------------------------
# NIST CSF
# ---------------------------------------------------------------------------

NIST_CSF_FUNCTIONS: dict[str, list[str]] = {
    "Identify": [
        "Asset Management",
        "Business Environment",
        "Governance",
        "Risk Assessment",
        "Risk Management Strategy",
        "Supply Chain Risk Management",
    ],
    "Protect": [
        "Identity Management and Access Control",
        "Awareness and Training",
        "Data Security",
        "Information Protection Processes and Procedures",
        "Maintenance",
        "Protective Technology",
    ],
    "Detect": [
        "Anomalies and Events",
        "Security Continuous Monitoring",
        "Detection Processes",
    ],
    "Respond": [
        "Response Planning",
        "Communications",
        "Analysis",
        "Mitigation",
        "Improvements",
    ],
    "Recover": [
        "Recovery Planning",
        "Improvements",
        "Communications",
    ],
}

NIST_SEVERITY_LEVELS: list[str] = [
    "Critical",
    "High",
    "Medium",
    "Low",
    "Informational",
]


def severity_score(level: str) -> int:
    return max(0, 5 - NIST_SEVERITY_LEVELS.index(level)) if level in NIST_SEVERITY_LEVELS else 0


# ---------------------------------------------------------------------------
# Common port-to-service mapping
# ---------------------------------------------------------------------------

PORT_SERVICE_MAP: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    1433: "MSSQL",
    1521: "Oracle DB",
    2049: "NFS",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    6379: "Redis",
    8080: "HTTP-Alt",
    8443: "HTTPS-Alt",
    27017: "MongoDB",
}


def service_for_port(port: int) -> str:
    return PORT_SERVICE_MAP.get(port, "Unknown")
