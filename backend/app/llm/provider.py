"""LLM Provider Abstraction — Ollama-first, with pluggable cloud fallback.

The LLM is a PRESENTATION LAYER. It explains structured ForecastResult
objects in natural language. It never decides anything about the prediction.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a text response from the LLM."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this provider is reachable."""
        ...


class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider."""

    def __init__(self, host: str | None = None, model: str | None = None) -> None:
        self.host = host or settings.OLLAMA_HOST
        self.model = model or settings.OLLAMA_MODEL

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate response via Ollama API."""
        try:
            import ollama
            client = ollama.AsyncClient(host=self.host)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await client.chat(model=self.model, messages=messages)
            return response["message"]["content"]

        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            import ollama
            client = ollama.AsyncClient(host=self.host)
            await client.list()
            return True
        except Exception:
            return False


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (fallback)."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key or (settings.OPENAI_API_KEY if settings.has_openai else None)
        self.model = model

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise

    async def is_available(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0


class LLMProviderFactory:
    """Factory for creating the appropriate LLM provider.

    Priority order:
    1. Ollama (local, free, private)
    2. OpenAI (cloud fallback)
    """

    @staticmethod
    async def get_provider() -> LLMProvider:
        """Get the best available LLM provider."""
        # Try Ollama first
        ollama = OllamaProvider()
        if await ollama.is_available():
            logger.info(f"Using Ollama ({ollama.model}) at {ollama.host}")
            return ollama

        # Fallback to OpenAI
        if settings.has_openai:
            openai = OpenAIProvider()
            logger.info("Using OpenAI as fallback")
            return openai

        logger.warning("No LLM provider available — explanations will be unavailable")
        raise RuntimeError("No LLM provider available. Start Ollama or configure OPENAI_API_KEY.")

    @staticmethod
    def get_provider_sync(provider_name: str = "ollama") -> LLMProvider:
        """Get a specific provider by name (no availability check)."""
        if provider_name == "ollama":
            return OllamaProvider()
        elif provider_name == "openai":
            return OpenAIProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
