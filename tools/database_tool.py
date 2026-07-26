"""
DatabaseTool — PostgreSQL query execution.

Executes read-only SQL queries against a PostgreSQL database using
the configured connection string. Write operations (INSERT, UPDATE,
DELETE, DROP, etc.) are blocked to prevent accidental data mutation.

Requires the `DATABASE_URL` environment variable to be set.
"""

from typing import Optional
import asyncpg

from tools.base import BaseTool
from config.settings import settings

BLOCKED_KEYWORDS = {"insert", "update", "delete", "drop", "truncate", "alter", "create", "grant", "revoke"}


def _is_read_only(query: str) -> bool:
    cleaned = query.strip().lower()
    for kw in BLOCKED_KEYWORDS:
        if cleaned.startswith(kw):
            return False
    return True


class DatabaseQueryTool(BaseTool):
    name = "database_query"
    description = "Execute a read-only SQL query against the PostgreSQL database. Only SELECT queries are allowed."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The SQL query to execute (SELECT only)",
            },
            "params": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional query parameters",
            },
        },
        "required": ["query"],
    }

    async def execute(self, query: str, params: Optional[list] = None) -> str:
        if not _is_read_only(query):
            raise PermissionError("Only SELECT queries are allowed")

        conn = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
        try:
            if params:
                rows = await conn.fetch(query, *params)
            else:
                rows = await conn.fetch(query)

            if not rows:
                return "Query returned no results."

            columns = [desc.name for desc in rows[0].keys()] if rows else []
            result = []
            for row in rows:
                result.append({col: str(row[col]) for col in columns})
            import json
            return json.dumps(result, indent=2)
        finally:
            await conn.close()
