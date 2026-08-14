"""
settings_manager.py — Runtime Settings Read/Write
===================================================
Reads and writes the AI Hub configuration from/to the AppDaemon apps.yaml
file at runtime, allowing the React frontend to change LLM providers,
models, API keys, and per-agent model overrides without SSH access.

Security model:
  - API keys are stored in /config/secrets.yaml (HA's secret store).
  - This manager writes ONLY to apps.yaml (the AppDaemon app config).
  - It never writes raw key values into apps.yaml — it always uses the
    !secret tag pattern so secrets stay in secrets.yaml.
  - The frontend sends key values; this manager writes them to secrets.yaml
    via a separate, carefully scoped write operation.

File paths:
  - apps.yaml:     /config/appdaemon/apps/ai_hub/apps.yaml
  - secrets.yaml:  /config/secrets.yaml

Both paths are auto-detected relative to this file's location.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_hub")

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

# This file lives at /config/appdaemon/apps/ai_hub/settings_manager.py
_THIS_DIR = Path(__file__).parent
_APPS_YAML = _THIS_DIR / "apps.yaml"
_SECRETS_YAML = _THIS_DIR.parents[2] / "secrets.yaml"  # /config/secrets.yaml

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

# Supported providers and their model lists
PROVIDER_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4-turbo",
        "o1",
        "o1-mini",
        "o3-mini",
    ],
    "gemini": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
    "anthropic": [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-opus-4",
        "claude-sonnet-4",
        "claude-3-5-sonnet-20241022",
    ],
    "openrouter": [
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-2.5-pro",
        "meta-llama/llama-3.1-405b-instruct",
        "mistralai/mistral-large",
        "custom",  # user can type any openrouter slug
    ],
}

# ---------------------------------------------------------------------------
# Settings schema
# ---------------------------------------------------------------------------

def get_default_settings() -> dict[str, Any]:
    """Return the default settings structure."""
    return {
        "active_llm_provider": "openai",
        "active_llm_model": "gpt-4o",
        "github_branch": "main",
        "github_repo_owner": "",
        "github_repo_name": "",
        # Per-agent model overrides (empty = use global model)
        "agent_overrides": {agent: {"provider": "", "model": ""} for agent in AGENT_ROLES},
        # API key presence flags (never return actual key values to the frontend)
        "keys_configured": {
            "openai": False,
            "gemini": False,
            "anthropic": False,
            "openrouter": False,
            "github_pat": False,
            "appdaemon_token": False,
        },
    }


# ---------------------------------------------------------------------------
# apps.yaml reader
# ---------------------------------------------------------------------------

def _read_apps_yaml_raw() -> str:
    """Read the raw apps.yaml content."""
    if not _APPS_YAML.exists():
        raise FileNotFoundError(f"apps.yaml not found at {_APPS_YAML}")
    return _APPS_YAML.read_text(encoding="utf-8")


def _read_secrets_yaml_raw() -> str:
    """Read the raw secrets.yaml content."""
    if not _SECRETS_YAML.exists():
        return ""
    return _SECRETS_YAML.read_text(encoding="utf-8")


def _get_secret_value(key: str) -> str:
    """Extract a secret value from secrets.yaml by key."""
    content = _read_secrets_yaml_raw()
    pattern = rf'^{re.escape(key)}\s*:\s*["\']?([^"\'\n]+)["\']?\s*$'
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def _secret_is_configured(key: str) -> bool:
    """Return True if the secret exists and is not a placeholder."""
    value = _get_secret_value(key)
    return bool(value) and not value.startswith("REPLACE_WITH") and not value.startswith("YOUR_")


def _get_apps_yaml_value(key: str) -> str:
    """Extract a plain value from apps.yaml by key (non-secret fields)."""
    content = _read_apps_yaml_raw()
    pattern = rf'^\s+{re.escape(key)}\s*:\s*["\']?([^"\'\n#]+)["\']?'
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_settings() -> dict[str, Any]:
    """
    Load current settings from apps.yaml and secrets.yaml.

    Returns a dict safe to send to the frontend:
      - Non-sensitive config values are returned as-is
      - API keys are NEVER returned; only a boolean 'is configured' flag
      - Per-agent overrides are read from apps.yaml agent_overrides section
    """
    settings = get_default_settings()

    try:
        settings["active_llm_provider"] = _get_apps_yaml_value("active_llm_provider") or "openai"
        settings["active_llm_model"] = _get_apps_yaml_value("active_llm_model") or "gpt-4o"
        settings["github_branch"] = _get_apps_yaml_value("github_branch") or "main"
        settings["github_repo_owner"] = _get_secret_value("github_repo_owner")
        settings["github_repo_name"] = _get_secret_value("github_repo_name")

        # Check which keys are configured
        settings["keys_configured"] = {
            "openai": _secret_is_configured("openai_api_key"),
            "gemini": _secret_is_configured("gemini_api_key"),
            "anthropic": _secret_is_configured("anthropic_api_key"),
            "openrouter": _secret_is_configured("openrouter_api_key"),
            "github_pat": _secret_is_configured("github_pat"),
            "appdaemon_token": _secret_is_configured("appdaemon_token"),
        }

        # Per-agent overrides
        for agent in AGENT_ROLES:
            provider = _get_apps_yaml_value(f"agent_{agent}_provider")
            model = _get_apps_yaml_value(f"agent_{agent}_model")
            settings["agent_overrides"][agent] = {
                "provider": provider,
                "model": model,
            }

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load settings: %s", exc)

    return settings


def save_settings(payload: dict[str, Any]) -> dict[str, str]:
    """
    Save settings from the frontend payload.

    Writes:
      - Non-secret config (provider, model, branch) → apps.yaml
      - API keys (if provided and non-empty) → secrets.yaml
      - Per-agent overrides → apps.yaml

    Returns {"status": "ok"} or {"status": "error", "message": "..."}.
    """
    try:
        # ── Write non-secret values to apps.yaml ──────────────────────
        apps_updates: dict[str, str] = {}

        if "active_llm_provider" in payload:
            apps_updates["active_llm_provider"] = str(payload["active_llm_provider"])
        if "active_llm_model" in payload:
            apps_updates["active_llm_model"] = str(payload["active_llm_model"])
        if "github_branch" in payload:
            apps_updates["github_branch"] = str(payload["github_branch"])

        # Per-agent overrides
        overrides: dict[str, dict] = payload.get("agent_overrides", {})
        for agent, cfg in overrides.items():
            if agent in AGENT_ROLES:
                apps_updates[f"agent_{agent}_provider"] = str(cfg.get("provider", ""))
                apps_updates[f"agent_{agent}_model"] = str(cfg.get("model", ""))

        if apps_updates:
            _update_apps_yaml(apps_updates)

        # ── Write secrets to secrets.yaml ─────────────────────────────
        secrets_updates: dict[str, str] = {}

        key_map = {
            "openai_api_key": payload.get("openai_api_key", ""),
            "gemini_api_key": payload.get("gemini_api_key", ""),
            "anthropic_api_key": payload.get("anthropic_api_key", ""),
            "openrouter_api_key": payload.get("openrouter_api_key", ""),
            "github_pat": payload.get("github_pat", ""),
            "github_repo_owner": payload.get("github_repo_owner", ""),
            "github_repo_name": payload.get("github_repo_name", ""),
            "appdaemon_token": payload.get("appdaemon_token", ""),
        }

        for key, value in key_map.items():
            if value and value.strip() and not value.startswith("•"):
                # Only write non-empty values that aren't the masked placeholder
                secrets_updates[key] = value.strip()

        if secrets_updates:
            _update_secrets_yaml(secrets_updates)

        logger.info("Settings saved: %d apps.yaml keys, %d secrets", len(apps_updates), len(secrets_updates))
        return {"status": "ok", "message": "Settings saved. Restart AppDaemon add-on to apply LLM changes."}

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save settings: %s", exc)
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# File update helpers
# ---------------------------------------------------------------------------

def _update_apps_yaml(updates: dict[str, str]) -> None:
    """
    Update key-value pairs in apps.yaml.
    For existing keys: replaces the value in-place.
    For new keys: appends them under the ai_hub_orchestrator block.
    """
    content = _read_apps_yaml_raw()

    for key, value in updates.items():
        # Try to replace existing key
        pattern = rf'^(\s+{re.escape(key)}\s*:\s*)(.+)$'
        replacement = rf'\g<1>"{value}"'
        new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)

        if count > 0:
            content = new_content
        else:
            # Key doesn't exist — append before the last non-empty line of the block
            content = content.rstrip() + f'\n  {key}: "{value}"\n'

    # Atomic write: write to temp file then rename
    tmp = _APPS_YAML.with_suffix(".yaml.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(_APPS_YAML)
    logger.debug("apps.yaml updated: %s", list(updates.keys()))


def _update_secrets_yaml(updates: dict[str, str]) -> None:
    """
    Update key-value pairs in secrets.yaml.
    For existing keys: replaces the value in-place.
    For new keys: appends them at the end of the file.
    """
    if not _SECRETS_YAML.exists():
        raise FileNotFoundError(f"secrets.yaml not found at {_SECRETS_YAML}")

    content = _SECRETS_YAML.read_text(encoding="utf-8")

    for key, value in updates.items():
        # Escape special characters in the value
        safe_value = value.replace('"', '\\"')
        pattern = rf'^({re.escape(key)}\s*:\s*)(.+)$'
        replacement = rf'\g<1>"{safe_value}"'
        new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)

        if count > 0:
            content = new_content
        else:
            # Key doesn't exist — append
            content = content.rstrip() + f'\n{key}: "{safe_value}"\n'

    # Atomic write
    tmp = _SECRETS_YAML.with_suffix(".yaml.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(_SECRETS_YAML)
    logger.info("secrets.yaml updated: %s", list(updates.keys()))


# ---------------------------------------------------------------------------
# Metadata for the frontend
# ---------------------------------------------------------------------------

def get_metadata() -> dict[str, Any]:
    """Return static metadata the frontend needs to render the settings UI."""
    return {
        "agent_roles": AGENT_ROLES,
        "provider_models": PROVIDER_MODELS,
    }
