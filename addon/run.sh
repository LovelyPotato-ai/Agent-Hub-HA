#!/usr/bin/with-contenv bashio
# =============================================================================
# run.sh — AI Hub Add-on Entrypoint
# =============================================================================
# This script is executed by s6-overlay (the HA add-on process supervisor).
# It reads the add-on options from /data/options.json (written by the
# Supervisor from the add-on Configuration tab), exports them as environment
# variables, then starts the Python server.
#
# bashio is the HA add-on shell helper library — provides:
#   bashio::config <key>     — read a value from /data/options.json
#   bashio::log.info <msg>   — structured logging
#   bashio::exit.nok <msg>   — exit with error
# =============================================================================

bashio::log.info "Starting AI Hub..."

# ── Read configuration from add-on options ────────────────────────────────────
export AI_HUB_LLM_PROVIDER="$(bashio::config 'active_llm_provider')"
export AI_HUB_LLM_MODEL="$(bashio::config 'active_llm_model')"
export AI_HUB_OPENAI_KEY="$(bashio::config 'openai_api_key')"
export AI_HUB_GEMINI_KEY="$(bashio::config 'gemini_api_key')"
export AI_HUB_ANTHROPIC_KEY="$(bashio::config 'anthropic_api_key')"
export AI_HUB_OPENROUTER_KEY="$(bashio::config 'openrouter_api_key')"
export AI_HUB_GITHUB_PAT="$(bashio::config 'github_pat')"
export AI_HUB_GITHUB_OWNER="$(bashio::config 'github_repo_owner')"
export AI_HUB_GITHUB_REPO="$(bashio::config 'github_repo_name')"
export AI_HUB_GITHUB_BRANCH="$(bashio::config 'github_branch')"
export AI_HUB_LOG_LEVEL="$(bashio::config 'log_level')"

# ── HA Supervisor connection ───────────────────────────────────────────────────
# SUPERVISOR_TOKEN is injected automatically by the Supervisor into every add-on.
# The server uses it to authenticate with the HA REST API.
if [ -z "${SUPERVISOR_TOKEN}" ]; then
    bashio::exit.nok "SUPERVISOR_TOKEN is not set. Is hassio_api enabled in config.yaml?"
fi
export AI_HUB_SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"

# ── Server port ───────────────────────────────────────────────────────────────
# Must match ingress_port in config.yaml
export AI_HUB_PORT="8099"

# ── Data directory ────────────────────────────────────────────────────────────
# /data persists across add-on restarts (used by settings_manager.py)
export AI_HUB_DATA_DIR="/data"

bashio::log.info "LLM provider: ${AI_HUB_LLM_PROVIDER}, model: ${AI_HUB_LLM_MODEL}"
bashio::log.info "Starting server on port ${AI_HUB_PORT}..."

# ── Start the Python server ───────────────────────────────────────────────────
exec python3 /app/server.py
