import logging
from typing import Optional

logger = logging.getLogger("tools.execution.policy")


class ExecutionPolicy:
    def __init__(self, allowed_tools: Optional[list[str]] = None):
        self.allowed_tools = set(allowed_tools or [
            "file",
            "strings",
            "exiftool",
            "yara",
            "capa",
            "binwalk",
            "curl",
            "python",
        ])
        self.blocked_patterns = [
            "rm -rf",
            "mkfs",
            "dd if=",
            "> /dev/",
            "shutdown",
            "reboot",
            "sudo ",
            "su ",
            "chmod 777",
            "chown ",
            "passwd",
            "useradd",
            "deluser",
            "iptables",
            "route ",
            "ifconfig ",
            "wget ",
            "curl -o ",
            "curl --output",
            "nc -e",
            "ncat -e",
            "nmap",
            "hydra",
            "john ",
            "hashcat ",
            "aircrack",
            "metasploit",
            "msfvenom",
        ]

    def check_tool(self, tool_name: str) -> tuple[bool, str]:
        if tool_name not in self.allowed_tools:
            return False, f"Tool '{tool_name}' is not in the allowed list. Allowed: {sorted(self.allowed_tools)}"
        return True, ""

    def check_command(self, command: str) -> tuple[bool, str]:
        command_lower = command.lower()
        for pattern in self.blocked_patterns:
            if pattern.lower() in command_lower:
                return False, f"Command blocked by security policy: pattern '{pattern}' detected"
        return True, ""

    def allow_tool(self, tool_name: str) -> None:
        self.allowed_tools.add(tool_name)

    def block_tool(self, tool_name: str) -> None:
        self.allowed_tools.discard(tool_name)

    def get_allowed(self) -> list[str]:
        return sorted(self.allowed_tools)
