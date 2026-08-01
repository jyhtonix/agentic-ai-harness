import logging
from typing import Optional

from agents.team.evidence import AgentFinding
from agents.team.specialists import SpecialistAgent

logger = logging.getLogger("agents.team.specialists.binary_reverse")


class BinaryReverseAgent(SpecialistAgent):
    name = "binary_reverse_agent"
    category = "binary_reverse"
    capabilities = [
        "file_identification",
        "elf_analysis",
        "pe_analysis",
        "static_analysis",
        "dynamic_analysis",
        "function_identification",
        "control_flow_analysis",
        "decompilation",
        "assembly_analysis",
        "calling_convention_analysis",
        "symbol_analysis",
        "obfuscation_analysis",
        "packing_analysis",
        "anti_debugging_analysis",
        "malware_style_analysis",
    ]

    def __init__(self, tool_executor=None, tool_selector=None, skill_selector=None):
        super().__init__(tool_executor, tool_selector, skill_selector)

    async def analyze(self, task: str, context: Optional[dict] = None) -> AgentFinding:
        logger.info("BinaryReverseAgent analyzing: %.60s", task)
        ctx = self._build_context(task, context)
        c = ctx.lower()

        findings = []
        evidence = []
        tools_used = []
        confidence = 0.5

        if "file" in c and ("identif" in c or "format" in c or "type" in c):
            findings.append("File identification — run file(1) and check magic bytes before deeper analysis")
            evidence.append("Binary file type/format identified")
            tools_used.extend(["file", "readelf"])
            confidence += 0.15
        if "elf" in c or "readelf" in c:
            findings.append("ELF analysis — inspect headers, sections, and imports with readelf and objdump")
            evidence.append("ELF binary structure identified")
            tools_used.extend(["readelf", "objdump"])
            confidence += 0.15
        if "pe file" in c or "portable executable" in c or "windows executable" in c or "dll" in c or "exe" in c:
            findings.append("PE analysis — examine PE headers, sections, imports, and resources on the Windows target")
            evidence.append("PE binary structure identified")
            tools_used.extend(["objdump", "x64dbg"])
            confidence += 0.15
        if "static" in c or "strings" in c or "symbol" in c or "import" in c:
            findings.append("Static analysis — extract strings, symbols, and imports before tracing runtime behavior")
            evidence.append("Static surface enumerated (strings/symbols/imports)")
            tools_used.extend(["strings", "objdump", "ghidra"])
            confidence += 0.15
        if "dynamic" in c or "debug" in c or "trace" in c or "breakpoint" in c:
            findings.append("Dynamic analysis — step through execution in a debugger and observe runtime state")
            evidence.append("Dynamic/runtime behavior identified for tracing")
            tools_used.extend(["x64dbg", "gdb"])
            confidence += 0.15
        if "function" in c or "entry point" in c or "main" in c:
            findings.append("Function identification — map entry point and key functions to locate the flag-check logic")
            evidence.append("Key functions identified for analysis")
            tools_used.extend(["ghidra", "radare2"])
            confidence += 0.15
        if "control flow" in c or "cfg" in c or "branch" in c or "flow" in c:
            findings.append("Control flow analysis — reconstruct branches and loops to understand the decision logic")
            evidence.append("Control flow reconstructed for the target routine")
            tools_used.extend(["angr", "radare2"])
            confidence += 0.15
        if "decompil" in c or "pseudo" in c or "source" in c or "reconstruct" in c:
            findings.append("Decompilation — lift assembly to pseudo-C to reason about the algorithm at a higher level")
            evidence.append("Decompiled representation produced for review")
            tools_used.extend(["ghidra", "ida"])
            confidence += 0.15

        if "assembly" in c or "asm" in c or "x86" in c or "x64" in c or "instruction" in c:
            findings.append("Assembly review — read x86/x64 instructions and map them back to higher-level constructs")
            evidence.append("Assembly instruction set identified for the target")
            tools_used.extend(["objdump", "radare2"])
            confidence += 0.1
        if "calling convention" in c or "convention" in c:
            findings.append("Calling conventions — track argument registers (rdi/rsi/rdx) and stack usage across calls")
            evidence.append("Calling convention understood for the architecture")
            tools_used.append("ghidra")
            confidence += 0.1
        if "symbol" in c:
            findings.append("Symbol analysis — resolve symbol tables and strip/stub state to guide reverse engineering")
            evidence.append("Symbol table state assessed")
            tools_used.extend(["readelf", "ghidra"])
            confidence += 0.1
        if "obfusc" in c or "opaque" in c or "flatten" in c or "mba" in c:
            findings.append("Obfuscation analysis — deobfuscate control-flow flattening, opaque predicates, and mixed boolean arithmetic")
            evidence.append("Obfuscation technique identified for deobfuscation")
            tools_used.extend(["angr", "ghidra"])
            confidence += 0.15
        if "pack" in c or "upx" in c or "loader" in c or "compress" in c:
            findings.append("Packing analysis — detect the packer, unpack the binary, and re-inspect the recovered code")
            evidence.append("Packed target detected; unpacking required")
            tools_used.extend(["upx", "ghidra"])
            confidence += 0.15
        if "anti-debug" in c or "anti debug" in c or "ptrace" in c or "tamper" in c or "checksum" in c:
            findings.append("Anti-debugging analysis — identify ptrace/timing/checksum defenses and bypass them for analysis")
            evidence.append("Anti-debugging defense identified")
            tools_used.extend(["gdb", "x64dbg"])
            confidence += 0.15
        if "malware" in c or "malicious" in c or "rat" in c or "loader" in c or "dropper" in c:
            findings.append("Malware-style analysis — treat the binary as hostile; sandbox dynamic behavior and isolate effects")
            evidence.append("Malware-like behavior flagged for containment")
            tools_used.extend(["gdb", "x64dbg"])
            confidence += 0.15

        if not findings:
            findings.append("Performing general binary reverse engineering assessment — identify the target and select a static/dynamic strategy")
            evidence.append("General reverse engineering review performed")
            tools_used.append("strings")

        return AgentFinding(
            agent_name=self.name,
            findings=findings,
            evidence=list(set(evidence)),
            confidence=min(confidence, 0.95),
            tools_used=list(set(tools_used)),
            category=self.category,
        )
