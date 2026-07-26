"""
WebSearchTool — web search and content retrieval.

Searches the web using DuckDuckGo's HTML interface (no API key required)
and returns structured results with titles, URLs, and snippets.
"""

import json
import httpx
from bs4 import BeautifulSoup

from tools.base import BaseTool


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for information. Returns a list of results with titles, URLs, and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
            },
        },
        "required": ["query"],
    }

    async def execute(self, query: str, num_results: int = 5) -> str:
        url = f"https://html.duckduckgo.com/html/?q={query}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for item in soup.select(".result")[:num_results]:
            title_el = item.select_one(".result__title a")
            snippet_el = item.select_one(".result__snippet")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": title_el.get("href", ""),
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })

        if not results:
            return "No search results found."

        return json.dumps(results, indent=2)
