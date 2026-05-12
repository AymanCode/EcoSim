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
- GroqProvider: Remote API via Groq Cloud

Both expose the same async `complete()` interface so the rest of the
codebase doesn't care which backend is active.
"""

import json
import logging
import os
import re
import asyncio
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
        top_p: Optional[float] = None,
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
        top_p: Optional[float] = None,
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
        if top_p is not None:
            payload["top_p"] = top_p
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
        max_tokens: int = 1200,
        max_retries: Optional[int] = None,
        max_retry_wait_seconds: Optional[float] = None,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-nano-9b-v2:free")
        self.max_tokens = max_tokens
        self.max_retries = (
            int(os.getenv("ECOSIM_OPENROUTER_MAX_RETRIES", "12")) if max_retries is None else max_retries
        )
        self.max_retry_wait_seconds = (
            float(os.getenv("ECOSIM_OPENROUTER_MAX_RETRY_WAIT_SECONDS", "120"))
            if max_retry_wait_seconds is None
            else max_retry_wait_seconds
        )
        self.empty_response_retries = int(os.getenv("ECOSIM_OPENROUTER_EMPTY_RESPONSE_RETRIES", "1"))
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
        top_p: Optional[float] = None,
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
            "max_tokens": self.max_tokens,
        }
        if top_p is not None:
            payload["top_p"] = top_p
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if os.getenv("OPENROUTER_SITE_URL"):
            headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "")
        if os.getenv("OPENROUTER_APP_NAME"):
            headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME", "")

        attempt = 0
        empty_attempt = 0
        while True:
            resp = await self._client.post(
                self.BASE_URL,
                headers=headers,
                json=payload,
            )
            if resp.status_code == 429 and attempt < self.max_retries:
                wait_seconds = self._retry_after_seconds(resp, attempt)
                logger.warning(
                    "OpenRouter rate limit hit for %s; retrying in %.1fs (%s/%s)",
                    self.model,
                    wait_seconds,
                    attempt + 1,
                    self.max_retries,
                )
                print(
                    f"  [OpenRouter] rate limit hit; waiting {wait_seconds:.1f}s "
                    f"before retry {attempt + 1}/{self.max_retries}",
                    flush=True,
                )
                await asyncio.sleep(wait_seconds)
                attempt += 1
                continue
            if resp.status_code in {500, 502, 503, 504} and attempt < self.max_retries:
                wait_seconds = self._retry_after_seconds(resp, attempt)
                logger.warning(
                    "OpenRouter transient error %s for %s; retrying in %.1fs (%s/%s)",
                    resp.status_code,
                    self.model,
                    wait_seconds,
                    attempt + 1,
                    self.max_retries,
                )
                print(
                    f"  [OpenRouter] transient error {resp.status_code}; waiting {wait_seconds:.1f}s "
                    f"before retry {attempt + 1}/{self.max_retries}",
                    flush=True,
                )
                await asyncio.sleep(wait_seconds)
                attempt += 1
                continue
            if resp.status_code >= 400:
                break

            data = resp.json()
            content = self._extract_message_content(data)
            if content.strip() or empty_attempt >= self.empty_response_retries:
                return content
            empty_attempt += 1
            wait_seconds = self._retry_after_seconds(resp, attempt)
            logger.warning(
                "OpenRouter returned empty content for %s; retrying in %.1fs (%s/%s)",
                self.model,
                wait_seconds,
                empty_attempt,
                self.empty_response_retries,
            )
            print(
                f"  [OpenRouter] empty completion; waiting {wait_seconds:.1f}s "
                f"before retry {empty_attempt}/{self.empty_response_retries}",
                flush=True,
            )
            await asyncio.sleep(wait_seconds)

        if resp.status_code >= 400:
            self._log_error_response(resp)
        resp.raise_for_status()
        data = resp.json()
        return self._extract_message_content(data)

    def _extract_message_content(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            logger.warning("OpenRouter response for %s had no choices", self.model)
            return ""

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content:
            return content

        # Some reasoning-heavy providers expose text in provider-specific fields.
        for key in ("reasoning", "reasoning_content", "text"):
            value = message.get(key) or choices[0].get(key)
            if isinstance(value, str) and value:
                return value

        logger.warning(
            "OpenRouter response for %s had empty content; message keys=%s choice keys=%s",
            self.model,
            sorted(message.keys()),
            sorted(choices[0].keys()),
        )
        return ""

    def _retry_after_seconds(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), self.max_retry_wait_seconds))
            except ValueError:
                pass

        text = response.text or ""
        match = re.search(r"try again in\s+([0-9.]+)\s*([smh]?)", text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            if unit == "m":
                value *= 60.0
            elif unit == "h":
                value *= 3600.0
            return max(0.0, min(value, self.max_retry_wait_seconds))

        backoff = min(2.0 * (2**attempt), self.max_retry_wait_seconds)
        return max(1.0, backoff)

    def _log_error_response(self, response: httpx.Response) -> None:
        text = (response.text or "").replace(self.api_key, "[REDACTED]")
        if len(text) > 500:
            text = text[:500] + "..."
        logger.warning("OpenRouter error response %s for %s: %s", response.status_code, self.model, text)

    async def close(self):
        await self._client.aclose()


class GroqProvider(LLMProvider):
    """Remote LLM inference via Groq's OpenAI-compatible Chat Completions API."""

    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        timeout: float = 60.0,
        max_tokens: int = 1200,
        max_retries: Optional[int] = None,
        max_retry_wait_seconds: Optional[float] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = (
            int(os.getenv("ECOSIM_GROQ_MAX_RETRIES", "12")) if max_retries is None else max_retries
        )
        self.max_retry_wait_seconds = (
            float(os.getenv("ECOSIM_GROQ_MAX_RETRY_WAIT_SECONDS", "120"))
            if max_retry_wait_seconds is None
            else max_retry_wait_seconds
        )
        self._client = httpx.AsyncClient(timeout=timeout)

    @property
    def name(self) -> str:
        return f"groq/{self.model}"

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            resp = await self._client.get(
                f"{self.BASE_URL}/models",
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
        top_p: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY not set. Add it to .env or environment.")

        max_tokens = self.max_tokens
        if self.model.startswith("openai/gpt-oss"):
            max_tokens = min(max_tokens, int(os.getenv("ECOSIM_GROQ_GPT_OSS_MAX_TOKENS", "700")))

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.model.startswith("openai/gpt-oss"):
            # GPT-OSS chat responses may include separate reasoning fields by default.
            # Keep this provider aligned with the rest of EcoSim's text-only parser.
            payload["include_reasoning"] = False
            payload["reasoning_effort"] = os.getenv("ECOSIM_GROQ_GPT_OSS_REASONING_EFFORT", "low")
        if top_p is not None:
            payload["top_p"] = top_p
        if response_format and not self.model.startswith("openai/gpt-oss"):
            payload["response_format"] = response_format

        attempted_format_fallback = False
        token_budget_reductions = 0
        last_response: Optional[httpx.Response] = None
        attempt = 0
        while attempt <= self.max_retries:
            resp = await self._client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if (
                resp.status_code == 400
                and response_format is not None
                and "response_format" in payload
                and self.model.startswith("openai/gpt-oss")
                and not attempted_format_fallback
            ):
                attempted_format_fallback = True
                payload.pop("response_format", None)
                logger.warning(
                    "Groq GPT-OSS rejected response_format for %s; retrying without response_format",
                    self.model,
                )
                print(
                    "  [Groq] GPT-OSS rejected response_format; retrying with prompt-only JSON",
                    flush=True,
                )
                continue
            if (
                resp.status_code == 413
                and self.model.startswith("openai/gpt-oss")
                and int(payload.get("max_tokens", 0) or 0) > 500
                and token_budget_reductions < 3
            ):
                token_budget_reductions += 1
                old_max_tokens = int(payload["max_tokens"])
                payload["max_tokens"] = max(500, int(old_max_tokens * 0.75))
                logger.warning(
                    "Groq GPT-OSS request too large for %s; reducing max_tokens from %s to %s",
                    self.model,
                    old_max_tokens,
                    payload["max_tokens"],
                )
                print(
                    f"  [Groq] GPT-OSS request too large; reducing max_tokens "
                    f"{old_max_tokens}->{payload['max_tokens']} and retrying",
                    flush=True,
                )
                continue
            if resp.status_code != 429:
                break
            last_response = resp
            if attempt >= self.max_retries:
                break
            wait_seconds = self._retry_after_seconds(resp, attempt)
            logger.warning(
                "Groq rate limit hit for %s; retrying in %.1fs (%s/%s)",
                self.model,
                wait_seconds,
                attempt + 1,
                self.max_retries,
            )
            print(
                f"  [Groq] rate limit hit; waiting {wait_seconds:.1f}s "
                f"before retry {attempt + 1}/{self.max_retries}",
                flush=True,
            )
            await asyncio.sleep(wait_seconds)
            attempt += 1

        if resp.status_code >= 400:
            self._log_error_response(resp)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"].get("content") or ""

    def _retry_after_seconds(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), self.max_retry_wait_seconds))
            except ValueError:
                pass

        text = response.text or ""
        match = re.search(r"try again in\s+([0-9.]+)\s*([smh]?)", text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            if unit == "m":
                value *= 60.0
            elif unit == "h":
                value *= 3600.0
            return max(0.0, min(value, self.max_retry_wait_seconds))

        backoff = min(2.0 * (2**attempt), self.max_retry_wait_seconds)
        return max(1.0, backoff)

    def _log_error_response(self, response: httpx.Response) -> None:
        text = (response.text or "").replace(self.api_key, "[REDACTED]")
        if len(text) > 500:
            text = text[:500] + "..."
        logger.warning("Groq error response %s for %s: %s", response.status_code, self.model, text)

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
        top_p: Optional[float] = None,
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
        if top_p is not None:
            payload["top_p"] = top_p
        # LM Studio/llama.cpp compatibility varies. Opt in when the local server supports it.
        if response_format is not None and os.getenv("ECOSIM_LLM_RESPONSE_FORMAT", "0") == "1":
            payload["response_format"] = response_format

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

    if config.provider == "groq":
        groq = GroqProvider(
            model=getattr(config, "groq_model", config.government_model),
            max_tokens=getattr(config, "government_max_tokens", 1200),
        )
        if await groq.health_check():
            logger.info("Using Groq provider: %s", groq.name)
            return groq
        logger.warning("Groq not available or GROQ_API_KEY is not set")
        await groq.close()

    openrouter = OpenRouterProvider(model=config.openrouter_model)
    if await openrouter.health_check():
        logger.info("Using OpenRouter provider: %s", openrouter.name)
        return openrouter

    logger.error("No LLM provider available (Ollama down, no Groq/OpenRouter key)")
    await openrouter.close()
    raise RuntimeError(
        "No LLM provider available. Start Ollama or set GROQ_API_KEY/OPENROUTER_API_KEY."
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
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

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

    # Try extracting a balanced JSON object while respecting strings.
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(brace_start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break

    return None
