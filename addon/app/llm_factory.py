"""
llm_factory.py — Configurable LLM Provider Factory
=====================================================
Returns a LangChain BaseChatModel instance for the requested provider.

Supported providers:
  openai      → ChatOpenAI (api.openai.com)
  gemini      → ChatGoogleGenerativeAI (generativelanguage.googleapis.com)
  anthropic   → ChatAnthropic (api.anthropic.com)
  openrouter  → ChatOpenAI with base_url override (openrouter.ai/api/v1)

Usage:
  from llm_factory import get_llm
  llm = get_llm(provider="openai", model="gpt-4o", api_key="sk-...")

Switching providers requires only a secrets.yaml change + add-on restart.
No Python code changes needed.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("ai_hub")

# ---------------------------------------------------------------------------
# Supported provider registry
# ---------------------------------------------------------------------------
SUPPORTED_PROVIDERS = {"openai", "gemini", "anthropic", "openrouter"}

# Default temperature for all providers — low for deterministic code output
DEFAULT_TEMPERATURE = 0.2

# Default request timeout in seconds
DEFAULT_TIMEOUT = 120


def get_llm(
    provider: str,
    model: str,
    api_key: str,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> Any:
    """
    Build and return a LangChain chat model for the given provider.

    Args:
        provider:    One of 'openai', 'gemini', 'anthropic', 'openrouter'.
        model:       Provider-specific model slug (e.g. 'gpt-4o').
        api_key:     API key for the chosen provider.
        temperature: Sampling temperature (default 0.2 for code tasks).
        timeout:     HTTP request timeout in seconds (default 120).
        **kwargs:    Extra kwargs forwarded to the underlying LangChain class.

    Returns:
        A LangChain BaseChatModel instance ready for use in CrewAI agents.

    Raises:
        ValueError: If provider is unsupported or api_key is empty.
        ImportError: If the required LangChain package is not installed.
    """
    provider = provider.strip().lower()

    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Choose from: {sorted(SUPPORTED_PROVIDERS)}"
        )

    if not api_key or api_key.startswith("REPLACE_WITH"):
        raise ValueError(
            f"API key for provider '{provider}' is missing. "
            f"Set it in the add-on Configuration tab in Home Assistant."
        )

    logger.info("Building LLM: provider=%s, model=%s", provider, model)

    if provider == "openai":
        return _build_openai(model, api_key, temperature, timeout, **kwargs)

    if provider == "gemini":
        return _build_gemini(model, api_key, temperature, timeout, **kwargs)

    if provider == "anthropic":
        return _build_anthropic(model, api_key, temperature, timeout, **kwargs)

    if provider == "openrouter":
        return _build_openrouter(model, api_key, temperature, timeout, **kwargs)

    # Should never reach here due to the guard above, but satisfies type checkers
    raise ValueError(f"Unhandled provider: {provider}")


# ---------------------------------------------------------------------------
# Provider-specific builders
# ---------------------------------------------------------------------------

def _build_openai(
    model: str,
    api_key: str,
    temperature: float,
    timeout: int,
    **kwargs: Any,
) -> Any:
    """Build a ChatOpenAI instance for api.openai.com."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is not installed. "
            "Add it to python_packages in appdaemon.yaml."
        ) from exc

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        request_timeout=timeout,
        max_retries=3,
        **kwargs,
    )


def _build_gemini(
    model: str,
    api_key: str,
    temperature: float,
    timeout: int,
    **kwargs: Any,
) -> Any:
    """Build a ChatGoogleGenerativeAI instance for Google Gemini."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise ImportError(
            "langchain-google-genai is not installed. "
            "Add it to python_packages in appdaemon.yaml."
        ) from exc

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=temperature,
        request_timeout=timeout,
        max_retries=3,
        **kwargs,
    )


def _build_anthropic(
    model: str,
    api_key: str,
    temperature: float,
    timeout: int,
    **kwargs: Any,
) -> Any:
    """Build a ChatAnthropic instance for Anthropic Claude."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise ImportError(
            "langchain-anthropic is not installed. "
            "Add it to python_packages in appdaemon.yaml."
        ) from exc

    return ChatAnthropic(
        model=model,
        api_key=api_key,
        temperature=temperature,
        timeout=timeout,
        max_retries=3,
        **kwargs,
    )


def _build_openrouter(
    model: str,
    api_key: str,
    temperature: float,
    timeout: int,
    **kwargs: Any,
) -> Any:
    """
    Build a ChatOpenAI instance pointed at OpenRouter.
    OpenRouter is OpenAI-API-compatible, so we reuse ChatOpenAI with a
    custom base_url.  Any model slug from openrouter.ai/models works.
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is not installed. "
            "Add it to python_packages in appdaemon.yaml."
        ) from exc

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        request_timeout=timeout,
        max_retries=3,
        default_headers={
            # OpenRouter recommends these headers for attribution
            "HTTP-Referer": "https://homeassistant.local",
            "X-Title": "AI Hub HA",
        },
        **kwargs,
    )
