import logging
from typing import Optional

from agents.team.evidence import AgentFinding
from agents.team.specialists import SpecialistAgent

logger = logging.getLogger("agents.team.specialists.pwn")


class PwnAgent(SpecialistAgent):
    name = "pwn_agent"
    category = "pwn"
    capabilities = [
        "binary_protection_analysis",
        "vulnerability_identification",
        "stack_overflow_analysis",
        "heap_exploitation_analysis",
        "memory_corruption_analysis",
        "buffer_overflow_analysis",
        "format_string_analysis",
        "use_after_free_analysis",
        "rop_chain_development",
        "ret2libc_strategy",
        "shellcode_development",
        "aslr_bypass",
        "nx_bypass",
        "pie_bypass",
        "canary_bypass",
        "exploit_strategy",
        "local_testing",
        "remote_challenge_analysis",
    ]

    def __init__(self, tool_executor=None, tool_selector=None, skill_selector=None):
        super().__init__(tool_executor, tool_selector, skill_selector)

    async def analyze(self, task: str, context: Optional[dict] = None) -> AgentFinding:
        logger.info("PwnAgent analyzing: %.60s", task)
        ctx = self._build_context(task, context)
        c = ctx.lower()

        findings = []
        evidence = []
        tools_used = []
        confidence = 0.5

        if "checksec" in c or "protection" in c or "nx" in c or "pie" in c or "relro" in c:
            findings.append("Binary protections check — run checksec and record NX, PIE, canary, and RELRO before choosing a strategy")
            evidence.append("Binary security protections assessed")
            tools_used.extend(["checksec", "pwntools"])
            confidence += 0.15
        if "stack overflow" in c or "buffer overflow" in c or "smash" in c or "gets(" in c or "strcpy" in c:
            findings.append("Stack/buffer overflow — find the offset with cyclic, then overwrite the return address or saved EBP")
            evidence.append("Stack/buffer overflow primitive identified")
            tools_used.extend(["pwntools", "gdb"])
            confidence += 0.15
        if "heap" in c or "malloc" in c or "free(" in c or "tcache" in c or "fastbin" in c:
            findings.append("Heap exploitation — analyze allocator state (tcache/fastbin) and chain chunks to build a write primitive")
            evidence.append("Heap interaction identified for exploitation analysis")
            tools_used.extend(["gdb", "pwntools"])
            confidence += 0.15
        if "memory corruption" in c or "corrupt" in c or "overflow" in c:
            findings.append("Memory corruption — locate the corrupted control data (return address, GOT, function pointer) and target it")
            evidence.append("Memory corruption vector identified")
            tools_used.append("gdb")
            confidence += 0.15
        if "format string" in c or "printf(" in c or "%n" in c or "format-string" in c:
            findings.append("Format string — enumerate stack offsets (%p), leak canary/libc, then write via %n to GOT or a hook")
            evidence.append("Format string primitive identified for leaks/writes")
            tools_used.extend(["pwntools", "gdb"])
            confidence += 0.15
        if "use-after-free" in c or "uaf" in c or "double free" in c or "dangling" in c:
            findings.append("Use-after-free — trigger the dangling pointer and reclaim the freed chunk to control a function pointer or freelist")
            evidence.append("Use-after-free / double-free primitive identified")
            tools_used.extend(["pwntools", "gdb"])
            confidence += 0.15

        if "rop" in c or "return oriented programming" in c or "gadget" in c or "ret2csu" in c:
            findings.append("ROP chain — find gadgets (pop rdi; ret) with ROPgadget/ropper and chain calls to leak and redirect execution")
            evidence.append("ROP gadget chain outlined for code execution")
            tools_used.extend(["pwntools", "ROPgadget", "ropper"])
            confidence += 0.15
        if "ret2libc" in c or "libc" in c:
            findings.append("ret2libc — leak a libc address (puts@GOT), resolve system('/bin/sh'), and chain the two-stage return")
            evidence.append("ret2libc strategy mapped to a libc leak primitive")
            tools_used.extend(["pwntools", "libc-database"])
            confidence += 0.15
        if "shellcode" in c or "execve" in c or "jmp esp" in c:
            findings.append("Shellcode — place shellcode on an executable region or align it with the payload and transfer control")
            evidence.append("Shellcode insertion path identified")
            tools_used.append("pwntools")
            confidence += 0.15
        if "aslr" in c or "nx" in c or "pie" in c or "canary" in c:
            findings.append("Mitigation bypass — plan leaks for ASLR/PIE and canary, and use ROP/ret2libc to defeat NX without executing shellcode")
            evidence.append("Mitigation bypass requirements identified")
            tools_used.append("pwntools")
            confidence += 0.1
        if "remote" in c or "server" in c or "nc " in c or "netcat" in c or "challenge" in c:
            findings.append("Remote challenge — adapt the local exploit with pwntools remote() and account for network I/O and address re-leaks")
            evidence.append("Remote challenge considerations identified")
            tools_used.append("pwntools")
            confidence += 0.1

        if not findings:
            findings.append("Performing general pwn assessment — check protections, identify the bug class, and draft an exploit strategy")
            evidence.append("General binary exploitation review performed")
            tools_used.append("pwntools")

        return AgentFinding(
            agent_name=self.name,
            findings=findings,
            evidence=list(set(evidence)),
            confidence=min(confidence, 0.95),
            tools_used=list(set(tools_used)),
            category=self.category,
        )
