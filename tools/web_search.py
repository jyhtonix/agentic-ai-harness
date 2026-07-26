"""
Web search tool.

Purpose: Searches the web for information and returns results.
Uses DuckDuckGo's HTML interface (no API key required).
Results include titles, URLs, and snippets.

Clean architecture: Wraps external HTTP calls behind a simple
function. Agents call search() without knowing or caring which
search engine is used.
"""

from typing import Optional
import httpx
from bs4 import BeautifulSoup


async def search(query: str, num_results: int = 5) -> list[dict]:
    """Search the web and return a list of result dicts with title, url, snippet."""
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
    return results
