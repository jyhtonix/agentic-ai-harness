"""
LLM interface and client.

Purpose: Abstracts the LLM provider behind a clean interface with
token usage tracking. Returns usage metadata alongside response text
so the Agent can track total consumption across the lifecycle.

Clean architecture: Core logic depends on the abstract LLM interface.
The OpenAI implementation is an adapter that can be swapped.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from openai import AsyncOpenAI

from config.settings import settings


@dataclass
class LLMUsage:
    """Token consumption for a single LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Response from an LLM call, including metadata."""
    content: str
    usage: LLMUsage = field(default_factory=LLMUsage)


class LLM(ABC):
    """Abstract interface all LLM providers must implement."""

    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """Send a chat completion and return the response with usage."""
        ...


class OpenAILLM(LLM):
    """OpenAI-compatible LLM implementation with usage tracking."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.openai_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        choice = response.choices[0]
        usage_data = response.usage
        usage = LLMUsage(
            prompt_tokens=usage_data.prompt_tokens if usage_data else 0,
            completion_tokens=usage_data.completion_tokens if usage_data else 0,
            total_tokens=usage_data.total_tokens if usage_data else 0,
        )
        return LLMResponse(
            content=choice.message.content or "",
            usage=usage,
        )
