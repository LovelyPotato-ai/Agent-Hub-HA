#!/bin/bash
# =============================================================================
# run.sh — AI Hub Add-on Entrypoint
# =============================================================================
# Executed by s6-overlay v3 as a supervised longrun service.
# Uses plain bash + jq to read /data/options.json directly, avoiding
# with-contenv / bashio which call s6-overlay suexec and require PID 1.
# =============================================================================

set -e

OPTIONS="/data/options.json"

# ── Guard: options file must exist (written by Supervisor before addon starts) ─
if [ ! -f "${OPTIONS}" ]; then
    echo "[AI Hub] ERROR: ${OPTIONS} not found — Supervisor did not write options. Exiting."
    exit 1
fi

# ── Helper: read a value from /data/options.json ──────────────────────────────
config() {
    jq --raw-output ".$1 // empty" "${OPTIONS}"
}

echo "[AI Hub] Starting AI Hub..."

# ── Read configuration from add-on options ────────────────────────────────────
export AI_HUB_LLM_PROVIDER="$(config 'active_llm_provider')"
export AI_HUB_LLM_MODEL="$(config 'active_llm_model')"
export AI_HUB_OPENAI_KEY="$(config 'openai_api_key')"
export AI_HUB_GEMINI_KEY="$(config 'gemini_api_key')"
export AI_HUB_ANTHROPIC_KEY="$(config 'anthropic_api_key')"
export AI_HUB_OPENROUTER_KEY="$(config 'openrouter_api_key')"
export AI_HUB_GITHUB_PAT="$(config 'github_pat')"
export AI_HUB_GITHUB_OWNER="$(config 'github_repo_owner')"
export AI_HUB_GITHUB_REPO="$(config 'github_repo_name')"
export AI_HUB_GITHUB_BRANCH="$(config 'github_branch')"
export AI_HUB_LOG_LEVEL="$(config 'log_level')"

# ── HA Supervisor connection ───────────────────────────────────────────────────
# SUPERVISOR_TOKEN is injected automatically by the Supervisor into every add-on.
if [ -z "${SUPERVISOR_TOKEN:-}" ]; then
    echo "[AI Hub] WARNING: SUPERVISOR_TOKEN is not set — HA entity updates will be disabled."
fi
export AI_HUB_SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN:-}"

# ── Server port ───────────────────────────────────────────────────────────────
export AI_HUB_PORT="8099"

# ── Data directory ────────────────────────────────────────────────────────────
export AI_HUB_DATA_DIR="/data"

echo "[AI Hub] LLM provider: ${AI_HUB_LLM_PROVIDER}, model: ${AI_HUB_LLM_MODEL}"
echo "[AI Hub] Starting server on port ${AI_HUB_PORT}..."

# ── Start the Python server ───────────────────────────────────────────────────
exec python3 /app/server.py
