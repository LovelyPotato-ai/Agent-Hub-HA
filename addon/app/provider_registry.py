"""
provider_registry.py — Dynamic LLM Provider Registry
======================================================
Manages LLM provider definitions stored in /data/providers.json.

A provider definition contains:
  - id:            Unique identifier (slug)
  - name:          Display name
  - type:          One of: openai, openai_compatible, gemini, anthropic
  - base_url:      API base URL (required for openai_compatible)
  - api_key_field: Which options.json field holds the API key
  - models:        List of model slugs available for this provider
  - builtin:       True for seeded providers (cannot be deleted)
  - created_at:    ISO8601 timestamp
  - updated_at:    ISO8601 timestamp

Provider types map to LangChain classes in llm_factory.py:
  openai            → ChatOpenAI (api.openai.com)
  openai_compatible → ChatOpenAI with custom base_url (Ollama, LM Studio, etc.)
  gemini            → ChatGoogleGenerativeAI
  anthropic         → ChatAnthropic
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_hub.provider_registry")

DATA_DIR = Path(os.environ.get("AI_HUB_DATA_DIR", "/data"))
PROVIDERS_FILE = DATA_DIR / "providers.json"

VALID_TYPES = {"openai", "openai_compatible", "gemini", "anthropic"}

# ---------------------------------------------------------------------------
# Default (built-in) providers — seeded on first run
# ---------------------------------------------------------------------------

DEFAULT_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "openai",
        "name": "OpenAI",
        "type": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_field": "openai_api_key",
        "models": [
            "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini",
            "gpt-4-turbo", "o1", "o1-mini", "o3-mini",
        ],
        "builtin": True,
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "type": "gemini",
        "base_url": "",
        "api_key_field": "gemini_api_key",
        "models": [
            "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash",
            "gemini-1.5-pro", "gemini-1.5-flash",
        ],
        "builtin": True,
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "type": "anthropic",
        "base_url": "",
        "api_key_field": "anthropic_api_key",
        "models": [
            "claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5",
            "claude-opus-4", "claude-sonnet-4", "claude-3-5-sonnet-20241022",
        ],
        "builtin": True,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "type": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_field": "openrouter_api_key",
        "models": [
            "openai/gpt-4o", "anthropic/claude-3.5-sonnet",
            "google/gemini-2.5-pro", "meta-llama/llama-3.1-405b-instruct",
            "mistralai/mistral-large",
        ],
        "builtin": True,
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(name: str) -> str:
    """Convert a display name to a valid ID slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"provider-{uuid.uuid4().hex[:8]}"


def _read() -> list[dict[str, Any]]:
    if not PROVIDERS_FILE.exists():
        return []
    try:
        with PROVIDERS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to read providers.json: %s", exc)
        return []


def _write(providers: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PROVIDERS_FILE.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(providers, f, indent=2)
        tmp.replace(PROVIDERS_FILE)
    except Exception as exc:
        logger.error("Failed to write providers.json: %s", exc)
        raise


def _seed() -> None:
    """Seed default providers if the file doesn't exist or is empty."""
    if PROVIDERS_FILE.exists() and _read():
        return
    now = _now()
    providers = [
        {**p, "created_at": now, "updated_at": now}
        for p in DEFAULT_PROVIDERS
    ]
    _write(providers)
    logger.info("Seeded %d default providers", len(providers))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_providers() -> list[dict[str, Any]]:
    """Return all provider definitions. Seeds defaults if needed."""
    if not PROVIDERS_FILE.exists() or not _read():
        _seed()
    return _read()


def get_provider(provider_id: str) -> dict[str, Any] | None:
    """Return a single provider by ID, or None if not found."""
    for provider in list_providers():
        if provider["id"] == provider_id:
            return provider
    return None


def create_provider(data: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new custom provider.

    Required: name, type
    Optional: base_url, api_key_field, models
    """
    ptype = data.get("type", "openai_compatible")
    if ptype not in VALID_TYPES:
        raise ValueError(f"Invalid provider type '{ptype}'. Choose from: {sorted(VALID_TYPES)}")

    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Provider name is required")

    provider_id = _slugify(name)
    # Ensure unique ID
    existing_ids = {p["id"] for p in list_providers()}
    base_id = provider_id
    counter = 2
    while provider_id in existing_ids:
        provider_id = f"{base_id}-{counter}"
        counter += 1

    now = _now()
    provider: dict[str, Any] = {
        "id": provider_id,
        "name": name,
        "type": ptype,
        "base_url": str(data.get("base_url", "")),
        "api_key_field": str(data.get("api_key_field", f"{provider_id}_api_key")),
        "models": [str(m).strip() for m in data.get("models", []) if str(m).strip()],
        "builtin": False,
        "created_at": now,
        "updated_at": now,
    }
    providers = list_providers()
    providers.append(provider)
    _write(providers)
    logger.info("Created provider: %s (%s)", provider["name"], provider_id)
    return provider


def update_provider(provider_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing provider. Returns updated provider or None."""
    providers = list_providers()
    for i, provider in enumerate(providers):
        if provider["id"] == provider_id:
            # Built-in providers: can't change type/base_url, only name/models
            if "name" in data:
                provider["name"] = str(data["name"])
            if provider.get("builtin"):
                # Only allow model list edits for builtins
                if "models" in data:
                    provider["models"] = [str(m).strip() for m in data["models"] if str(m).strip()]
            else:
                # Custom providers: full edit
                if "type" in data and data["type"] in VALID_TYPES:
                    provider["type"] = data["type"]
                if "base_url" in data:
                    provider["base_url"] = str(data["base_url"])
                if "api_key_field" in data:
                    provider["api_key_field"] = str(data["api_key_field"])
                if "models" in data:
                    provider["models"] = [str(m).strip() for m in data["models"] if str(m).strip()]
            provider["updated_at"] = _now()
            providers[i] = provider
            _write(providers)
            logger.info("Updated provider: %s", provider_id)
            return provider
    return None


def delete_provider(provider_id: str) -> bool:
    """Delete a custom provider. Returns False if not found or built-in."""
    providers = list_providers()
    target = next((p for p in providers if p["id"] == provider_id), None)
    if not target:
        return False
    if target.get("builtin"):
        logger.warning("Cannot delete built-in provider: %s", provider_id)
        return False
    new_providers = [p for p in providers if p["id"] != provider_id]
    _write(new_providers)
    logger.info("Deleted provider: %s", provider_id)
    return True
