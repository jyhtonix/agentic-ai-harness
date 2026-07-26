"""
QA Agent.

Purpose: Tests code and verifies quality standards. This agent is the
quality assurance specialist — it reviews code for correctness, writes
and runs tests, and validates that outputs meet acceptance criteria.

Capabilities:
  - Code correctness review
  - Test case generation
  - Edge case identification
  - Quality scoring against criteria
  - Regression analysis
"""

import logging
from typing import Optional

from models.llm import LLM
from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.qa")

QA_SYSTEM_PROMPT = """You are a QA Agent. You verify code quality and
correctness through testing and analysis.

For each QA task:
1. Understand the requirements and acceptance criteria
2. Review the code for correctness, edge cases, and style
3. Generate relevant test cases (unit, integration, edge cases)
4. Verify outputs match expected behaviour
5. Score quality on: correctness, completeness, performance, readability

Output a structured QA report with:
- Quality score (0.0 - 1.0)
- Test coverage assessment
- Issues found (with severity)
- Recommendations for improvement
- Overall verdict: Pass / Conditional Pass / Fail"""


class QAAgent(SpecializedAgent):
    """Tests code and verifies quality."""

    def __init__(self, llm: LLM):
        super().__init__(
            name="qa",
            llm=llm,
            system_prompt=QA_SYSTEM_PROMPT,
        )

    async def process_task(self, task: str) -> str:
        """Review code quality and generate test cases."""
        logger.info("QA review: %.80s", task)

        messages = self._build_messages(
            f"QA task:\n{task}\n\n"
            f"Review the code or output for quality. Generate test cases, "
            f"identify edge cases, and provide a quality score."
        )
        return await self._llm_chat(messages, temperature=0.3)
