"""LLM client abstraction for orchestrator planning."""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate_plan(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> tuple[str, dict[str, int]]:
        """
        Call the LLM and return (content, usage_dict).

        usage_dict keys: prompt_tokens, completion_tokens, total_tokens
        """
        pass

    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass


class OpenRouterClient(LLMClient):
    """OpenRouter API client (supports many models via single endpoint)."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found. Set OPENROUTER_API_KEY env var."
            )
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def model_name(self) -> str:
        return self.model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def generate_plan(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> tuple[str, dict[str, int]]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Extract content and usage
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        usage_dict: dict[str, int] = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }

        return content, usage_dict

    async def close(self):
        await self._client.aclose()


class OpenAICompatibleClient(LLMClient):
    """Generic client for OpenAI-compatible APIs (OpenAI, Azure, local, etc.)."""

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}" if self.api_key else {},
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def model_name(self) -> str:
        return self.model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def generate_plan(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> tuple[str, dict[str, int]]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        usage_dict: dict[str, int] = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }

        return content, usage_dict

    async def close(self):
        await self._client.aclose()


def create_llm_client(model_name: str, config: dict[str, Any]) -> LLMClient:
    """
    Factory to create LLM client based on model name pattern.

    Args:
        model_name: e.g., "openrouter/anthropic/claude-3-sonnet",
                    "gpt-4", "claude-3-opus"
        config: may contain 'llm_api_key', 'llm_base_url', etc.

    Returns:
        LLMClient instance
    """
    # OpenRouter pattern: openrouter/<provider>/<model>
    if model_name.startswith("openrouter/"):
        api_key = config.get("llm_api_key") or os.getenv("OPENROUTER_API_KEY")
        return OpenRouterClient(model=model_name, api_key=api_key)

    # OpenAI default
    if model_name.startswith("gpt-") or "openai" in model_name:
        api_key = config.get("llm_api_key") or os.getenv("OPENAI_API_KEY")
        base_url = config.get("llm_base_url", "https://api.openai.com/v1")
        return OpenAICompatibleClient(
            model=model_name, base_url=base_url, api_key=api_key
        )

    # Anthropic via OpenRouter? or direct?
    # For now, require user to prefix with openrouter/ for Anthropic
    raise ValueError(
        f"Unsupported LLM model: {model_name}. "
        "Use 'openrouter/<model>' or configure custom client."
    )
