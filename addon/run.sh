#!/bin/bash
# =============================================================================
# run.sh — AI Hub Add-on Entrypoint
# =============================================================================
# Executed by s6-overlay as a supervised service via /etc/services.d/ai_hub/run.
# Uses plain bash + jq to read /data/options.json directly, avoiding
# with-contenv / bashio which call s6-overlay suexec and require PID 1.
# =============================================================================

# Do NOT use set -e — we want to handle errors gracefully and keep running.
# A non-zero exit from this script causes s6 to restart it (exit code 100).

OPTIONS="/data/options.json"

# ── Helper: read a value from /data/options.json ──────────────────────────────
config() {
    local key="$1"
    local default="${2:-}"
    if [ -f "${OPTIONS}" ]; then
        local val
        val=$(jq --raw-output ".${key} // empty" "${OPTIONS}" 2>/dev/null)
        if [ -n "${val}" ]; then
            echo "${val}"
        else
            echo "${default}"
        fi
    else
        echo "${default}"
    fi
}

echo "[AI Hub] Starting AI Hub..."

# ── Read configuration from add-on options ────────────────────────────────────
# /data/options.json is written by the HA Supervisor from the add-on
# Configuration tab. If it doesn't exist yet, use empty defaults.
export AI_HUB_LLM_PROVIDER="$(config 'active_llm_provider' 'openai')"
export AI_HUB_LLM_MODEL="$(config 'active_llm_model' 'gpt-4o')"
export AI_HUB_OPENAI_KEY="$(config 'openai_api_key' '')"
export AI_HUB_GEMINI_KEY="$(config 'gemini_api_key' '')"
export AI_HUB_ANTHROPIC_KEY="$(config 'anthropic_api_key' '')"
export AI_HUB_OPENROUTER_KEY="$(config 'openrouter_api_key' '')"
export AI_HUB_GITHUB_PAT="$(config 'github_pat' '')"
export AI_HUB_GITHUB_OWNER="$(config 'github_repo_owner' '')"
export AI_HUB_GITHUB_REPO="$(config 'github_repo_name' '')"
export AI_HUB_GITHUB_BRANCH="$(config 'github_branch' 'main')"
export AI_HUB_LOG_LEVEL="$(config 'log_level' 'info')"

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
