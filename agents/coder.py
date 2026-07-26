"""
Coding Agent.

Purpose: Writes, reviews, and debugs code across multiple languages.
This agent is the implementation specialist — it takes specifications
and produces working code, then debugs issues when things go wrong.

Capabilities:
  - Code generation from specifications
  - Code review and refactoring
  - Debugging and error analysis
  - Test generation
  - Multiple language support (Python, JS, etc.)
"""

import json
import logging
from typing import Optional

from models.llm import LLM
from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.coder")

CODER_SYSTEM_PROMPT = """You are a Coding Agent. You write clean, well-structured
code that follows best practices.

For each coding task:
1. Understand the requirements before writing code
2. Write readable, maintainable code with appropriate error handling
3. Include usage examples or tests
4. Explain your design decisions
5. If debugging, analyse the error first, then propose a fix

Output the code in clearly marked blocks with the language specified."""


class CodingAgent(SpecializedAgent):
    """Writes, reviews, and debugs code."""

    def __init__(self, llm: LLM, code_runner_tool=None):
        super().__init__(
            name="coder",
            llm=llm,
            system_prompt=CODER_SYSTEM_PROMPT,
        )
        self.code_runner = code_runner_tool

    async def process_task(self, task: str) -> str:
        """Process a coding task — write, review, or debug."""
        logger.info("Coding task: %.80s", task)

        messages = self._build_messages(
            f"Coding task:\n{task}\n\n"
            f"Write or analyse the code as requested."
        )
        code_output = await self._llm_chat(messages, temperature=0.3)

        # If we have a code runner, extract and test any code blocks
        if self.code_runner and "```" in code_output:
            tested = await self._run_code_blocks(code_output)
            if tested:
                code_output += f"\n\n---\n**Execution Results:**\n{tested}"

        return code_output

    async def _run_code_blocks(self, text: str) -> str:
        """Extract and execute Python code blocks from markdown."""
        results = []
        lines = text.split("\n")
        in_block = False
        block = []
        lang = ""

        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                lang = line.strip("`").strip()
                block = []
            elif line.startswith("```") and in_block:
                in_block = False
                code = "\n".join(block)
                if lang in ("python", "py", "") and code.strip():
                    try:
                        result = await self.code_runner(code)
                        out = result.get("stdout", "")
                        err = result.get("stderr", "")
                        if out or err:
                            results.append(f"--- {lang} block ---\n{out}{err}")
                    except Exception as e:
                        results.append(f"Execution error: {e}")
            elif in_block:
                block.append(line)

        return "\n".join(results)
