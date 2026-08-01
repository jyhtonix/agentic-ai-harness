"""
Embedding interface.

Purpose: Provides text embedding capabilities for semantic search
and memory retrieval. Follows the same interface pattern as LLM —
swap the provider without changing callers.
"""

from abc import ABC, abstractmethod
from typing import Optional

from openai import AsyncOpenAI

from config.settings import settings


class Embedder(ABC):
    """Abstract interface for generating text embeddings."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...


class OpenAIEmbedder(Embedder):
    """OpenAI embedding implementation (text-embedding-3-small)."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding
