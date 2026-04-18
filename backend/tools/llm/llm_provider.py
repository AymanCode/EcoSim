from pathlib import Path
import sys

TOOLS_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = TOOLS_ROOT.parent
for _candidate in (BACKEND_ROOT, TOOLS_ROOT, TOOLS_ROOT / 'analysis', TOOLS_ROOT / 'checks', TOOLS_ROOT / 'llm', TOOLS_ROOT / 'runners'):
    _candidate_str = str(_candidate)
    if _candidate_str not in sys.path:
        sys.path.insert(0, _candidate_str)
"""
LLM Provider Abstraction Layer

Provides a unified interface for LLM inference across multiple backends:
- OllamaProvider: Local model serving via Ollama (default)
- OpenRouterProvider: Remote API via OpenRouter (fallback)

Both expose the same async `complete()` interface so the rest of the
codebase doesn't care which backend is active.
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.4,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a chat completion request and return the response text.

        Args:
            system: System prompt.
            user: User prompt.
            temperature: Sampling temperature.
            response_format: Optional format hint (e.g. {"type": "json_object"}).

        Returns:
            Raw text response from the model.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and ready."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        ...


class OllamaProvider(LLMProvider):
    """Local LLM inference via Ollama's OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "phi4-mini-reasoning",
        timeout: float = 300.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def name(self) -> str:
        return f"ollama/{self.model}"

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            if resp.status_code != 200:
                return False
            models = resp.json().get("models", [])
            available = [m.get("name", "") for m in models]
            # Check if our model (or a prefix of it) is available
            model_base = self.model.split(":")[0]
            found = any(model_base in m for m in available)
            if not found:
                logger.warning(
                    "Ollama is running but model '%s' not found. Available: %s",
                    self.model,
                    available,
                )
            return found
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.4,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        if response_format and response_format.get("type") == "json_object":
            payload["format"] = "json"

        resp = await self._client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    async def close(self):
        await self._client.aclose()


class OpenRouterProvider(LLMProvider):
    """Remote LLM inference via OpenRouter API (free tier)."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nvidia/nemotron-nano-9b-v2:free",
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def name(self) -> str:
        return f"openrouter/{self.model}"

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            resp = await self._client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.4,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not set. Add it to .env or environment."
            )

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = await self._client.post(
            self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def close(self):
        await self._client.aclose()


class LMStudioProvider(LLMProvider):
    """Local LLM inference via LM Studio's OpenAI-compatible server (localhost:1234)."""

    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        model: str = "local-model",
        timeout: float = 600.0,
        max_tokens: int = 40000,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def name(self) -> str:
        return f"lmstudio/{self.model}"

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(f"{self.base_url}/v1/models")
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.4,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        import time
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        # LM Studio only supports response_format for models that explicitly handle it.
        # Skip it and rely on prompt-level JSON instructions + extract_json_from_response.

        if os.getenv("LLM_DEBUG"):
            print(f"\n  [DEBUG] Sending to LM Studio:")
            print(f"  [DEBUG] max_tokens={payload.get('max_tokens')}")
            print(f"  [DEBUG] system={payload['messages'][0]['content'][:100]}...")
            print(f"  [DEBUG] user={payload['messages'][1]['content'][:100]}...")

        t0 = time.perf_counter()
        resp = await self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        elapsed = time.perf_counter() - t0

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", "?")
        completion_tokens = usage.get("completion_tokens", "?")
        tok_per_sec = completion_tokens / elapsed if isinstance(completion_tokens, int) and elapsed > 0 else "?"
        logger.info(
            "LMStudio call: prompt=%s tokens, completion=%s tokens, %.1fs (%.1f tok/s)",
            prompt_tokens, completion_tokens, elapsed,
            tok_per_sec if isinstance(tok_per_sec, float) else 0,
        )
        tok_per_sec_str = f"{tok_per_sec:.1f}" if isinstance(tok_per_sec, float) else "?"
        print(
            f"  [LMStudio] {prompt_tokens} prompt + {completion_tokens} completion tokens "
            f"| {elapsed:.1f}s | {tok_per_sec_str} tok/s",
            flush=True,
        )

        return data["choices"][0]["message"]["content"]

    async def close(self):
        await self._client.aclose()


async def create_provider(config) -> LLMProvider:
    """Create the best available LLM provider.

    Tries Ollama first (local, free, fast). Falls back to OpenRouter
    if Ollama isn't running or the model isn't available.

    Args:
        config: LLMConfig dataclass with provider preferences.

    Returns:
        An LLMProvider instance ready for use.
    """
    if config.provider == "lmstudio":
        base_url = getattr(config, "lmstudio_base_url", "http://127.0.0.1:1234")
        lmstudio = LMStudioProvider(base_url=base_url, model=config.government_model)
        if await lmstudio.health_check():
            logger.info("Using LM Studio provider: %s", lmstudio.name)
            return lmstudio
        logger.warning("LM Studio not available (is it running on %s?)", base_url)
        await lmstudio.close()

    if config.provider == "ollama":
        ollama = OllamaProvider(
            base_url=config.ollama_base_url,
            model=config.government_model,
        )
        if await ollama.health_check():
            logger.info("Using Ollama provider: %s", ollama.name)
            return ollama
        logger.warning("Ollama not available, falling back to OpenRouter")
        await ollama.close()

    openrouter = OpenRouterProvider(model=config.openrouter_model)
    if await openrouter.health_check():
        logger.info("Using OpenRouter provider: %s", openrouter.name)
        return openrouter

    logger.error("No LLM provider available (Ollama down, no OpenRouter key)")
    await openrouter.close()
    raise RuntimeError(
        "No LLM provider available. Start Ollama or set OPENROUTER_API_KEY."
    )


def extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from LLM response text.

    Handles common LLM output patterns:
    - Raw JSON
    - JSON wrapped in ```json ... ``` code blocks
    - JSON with surrounding text/reasoning
    - Thinking tags (<think>...</think>) before the JSON

    Returns:
        Parsed dict, or None if no valid JSON found.
    """
    # Strip thinking tags if present
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Try raw parse first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting from markdown code block
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # Try finding first { ... } pair
    brace_start = text.find("{")
    if brace_start != -1:
        # Find matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break

    return None

