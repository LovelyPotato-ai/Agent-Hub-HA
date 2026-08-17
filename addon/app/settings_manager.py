"""
settings_manager.py — Add-on Settings Manager
===============================================
Adapted from the AppDaemon version.

Key differences:
  - Settings are read from /data/options.json (written by the HA Supervisor
    from the add-on Configuration tab). This is the standard HA add-on pattern.
  - Settings are written back to /data/options.json (the Supervisor re-reads
    this file on next restart, but we also update it immediately for the UI).
  - No secrets.yaml or apps.yaml — everything is in options.json.
  - /data/ is the add-on's persistent storage directory (survives restarts).

The Supervisor writes /data/options.json from the add-on's Configuration tab.
We read it for GET /api/settings and write it for POST /api/settings/save.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_hub.settings")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("AI_HUB_DATA_DIR", "/data"))
OPTIONS_FILE = DATA_DIR / "options.json"

# ---------------------------------------------------------------------------
# Known agents and their role labels (for the UI)
# ---------------------------------------------------------------------------

AGENT_ROLES = {
    "developer":     "Developer Agent (writes code)",
    "reviewer":      "Reviewer Agent (critiques code)",
    "devops":        "DevOps Agent (commits to GitHub)",
    "ha_automation": "HA Automation Agent (generates YAML)",
    "ha_assistant":  "HA Assistant Agent (surveys sensors)",
    "ha_applier":    "HA Applier Agent (commits automations)",
}

# ---------------------------------------------------------------------------
# Default options structure
# ---------------------------------------------------------------------------

DEFAULT_OPTIONS: dict[str, Any] = {
    "active_llm_provider": "openai",
    "active_llm_model": "gpt-4o",
    "openai_api_key": "",
    "gemini_api_key": "",
    "anthropic_api_key": "",
    "openrouter_api_key": "",
    "github_pat": "",
    "log_level": "info",
    # Per-agent overrides (stored as nested dict in options.json)
    "agent_overrides": {agent: {"provider": "", "model": ""} for agent in AGENT_ROLES},
}

# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def _read_options() -> dict[str, Any]:
    """Read /data/options.json. Returns defaults if file doesn't exist."""
    if not OPTIONS_FILE.exists():
        logger.warning("options.json not found at %s, using defaults", OPTIONS_FILE)
        return dict(DEFAULT_OPTIONS)
    try:
        with OPTIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as exc:
        logger.error("Failed to read options.json: %s", exc)
        return dict(DEFAULT_OPTIONS)


def _write_options(options: dict[str, Any]) -> None:
    """Write updated options back to /data/options.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OPTIONS_FILE.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(options, f, indent=2)
        tmp.replace(OPTIONS_FILE)
        logger.info("options.json updated")
    except Exception as exc:
        logger.error("Failed to write options.json: %s", exc)
        raise


def _key_is_configured(value: str) -> bool:
    """Return True if the value is a non-empty, non-placeholder string."""
    return bool(value) and not value.startswith("PASTE_") and not value.startswith("not_configured")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_settings() -> dict[str, Any]:
    """
    Load current settings from /data/options.json.

    Returns a dict safe to send to the frontend:
      - API keys are replaced with boolean 'keys_configured' flags
      - Per-agent overrides are included
      - Custom provider API keys are included in keys_configured
    """
    from provider_registry import list_providers

    options = _read_options()

    # Ensure agent_overrides exists
    if "agent_overrides" not in options:
        options["agent_overrides"] = {
            agent: {"provider": "", "model": ""} for agent in AGENT_ROLES
        }

    # Build keys_configured from built-in + custom providers
    keys_configured: dict[str, bool] = {
        "openai":     _key_is_configured(options.get("openai_api_key", "")),
        "gemini":     _key_is_configured(options.get("gemini_api_key", "")),
        "anthropic":  _key_is_configured(options.get("anthropic_api_key", "")),
        "openrouter": _key_is_configured(options.get("openrouter_api_key", "")),
        "github_pat": _key_is_configured(options.get("github_pat", "")),
    }
    # Add custom provider keys
    for provider in list_providers():
        if not provider.get("builtin"):
            field = provider.get("api_key_field", "")
            if field:
                keys_configured[field] = _key_is_configured(options.get(field, ""))

    return {
        "active_llm_provider": options.get("active_llm_provider", "openai"),
        "active_llm_model":    options.get("active_llm_model", "gpt-4o"),
        "agent_overrides":     options.get("agent_overrides", {}),
        "keys_configured":     keys_configured,
    }


def save_settings(payload: dict[str, Any]) -> dict[str, str]:
    """
    Save settings from the frontend payload to /data/options.json.

    Only updates fields that are present in the payload.
    API keys are only written if they are non-empty and not masked (••••).

    Returns {"status": "ok"} or {"status": "error", "message": "..."}.
    """
    try:
        options = _read_options()

        # ── Non-secret config ──────────────────────────────────────────
        if "active_llm_provider" in payload:
            options["active_llm_provider"] = str(payload["active_llm_provider"])
        if "active_llm_model" in payload:
            options["active_llm_model"] = str(payload["active_llm_model"])

        # ── Per-agent overrides ────────────────────────────────────────
        overrides: dict[str, dict] = payload.get("agent_overrides", {})
        if overrides:
            if "agent_overrides" not in options:
                options["agent_overrides"] = {}
            for agent, cfg in overrides.items():
                if agent in AGENT_ROLES:
                    options["agent_overrides"][agent] = {
                        "provider": str(cfg.get("provider", "")),
                        "model":    str(cfg.get("model", "")),
                    }

        # ── API keys (only write non-empty, non-masked values) ─────────
        from provider_registry import list_providers

        # Built-in keys
        key_fields = {
            "openai_api_key":     payload.get("openai_api_key", ""),
            "gemini_api_key":     payload.get("gemini_api_key", ""),
            "anthropic_api_key":  payload.get("anthropic_api_key", ""),
            "openrouter_api_key": payload.get("openrouter_api_key", ""),
            "github_pat":         payload.get("github_pat", ""),
        }
        # Custom provider keys
        for provider in list_providers():
            if not provider.get("builtin"):
                field = provider.get("api_key_field", "")
                if field and field in payload:
                    key_fields[field] = payload[field]

        for key, value in key_fields.items():
            if value and value.strip() and not value.startswith("•"):
                options[key] = value.strip()

        _write_options(options)

        return {
            "status": "ok",
            "message": (
                "Settings saved to /data/options.json. "
                "Restart the add-on to apply LLM provider changes."
            ),
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save settings: %s", exc)
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Metadata for the frontend
# ---------------------------------------------------------------------------

def get_metadata() -> dict[str, Any]:
    """Return metadata the frontend needs to render the settings UI."""
    from provider_registry import list_providers

    providers = list_providers()
    provider_models: dict[str, list[str]] = {}
    for p in providers:
        provider_models[p["id"]] = p.get("models", [])

    return {
        "agent_roles":    AGENT_ROLES,
        "provider_models": provider_models,
    }
