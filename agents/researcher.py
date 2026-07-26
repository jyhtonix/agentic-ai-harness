"""
Research Agent.

Purpose: Gathers and synthesises information on a given topic.
Uses web search tools to find relevant data and the LLM to produce
concise, factual summaries. This agent is the knowledge-gathering
specialist in the multi-agent system.

Capabilities:
  - Web search and content extraction
  - Multi-source information synthesis
  - Citation tracking
  - Gap identification
"""

import json
import logging
from typing import Optional

from models.llm import LLM
from core.specialized import SpecializedAgent

logger = logging.getLogger("agent.researcher")

RESEARCHER_SYSTEM_PROMPT = """You are a Research Agent. Your job is to gather
relevant information and produce concise, factual summaries.

For each research task:
1. Identify the key questions that need answering
2. Search for relevant and current information
3. Synthesise findings from multiple sources
4. Cite sources where possible
5. Flag information gaps or uncertainties

Output a well-structured research report with sections for:
- Summary
- Key Findings
- Sources
- Gaps / Uncertainties"""


class ResearchAgent(SpecializedAgent):
    """Gathers and synthesises information using web search and LLM reasoning."""

    def __init__(self, llm: LLM, web_search_tool=None):
        super().__init__(
            name="researcher",
            llm=llm,
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
        )
        self.web_search = web_search_tool

    async def process_task(self, task: str) -> str:
        """Research a topic and return a structured report."""
        logger.info("Researching: %.80s", task)

        search_results = ""
        if self.web_search:
            try:
                results = await self.web_search(task)
                search_results = json.dumps(results, indent=2)
                logger.info("Web search returned %d results", len(results))
            except Exception as e:
                logger.warning("Web search failed: %s", e)
                search_results = "Web search unavailable."

        messages = self._build_messages(
            f"Research task: {task}\n\n"
            f"Web search results:\n{search_results}\n\n"
            f"Produce a comprehensive research report."
        )
        return await self._llm_chat(messages, temperature=0.4)
