#!/usr/bin/env bash
# =============================================================================
# install_via_web_terminal.sh
# =============================================================================
# Run this INSIDE the HA Web Terminal (Settings → Add-ons → Terminal & SSH
# → Open Web UI).
#
# This script installs the AI Hub by downloading the files directly from
# your GitHub repository onto the HA device.
#
# BEFORE RUNNING:
#   1. Push this project to a GitHub repository (public or private)
#   2. Replace GITHUB_USER and GITHUB_REPO below with your values
#   3. If the repo is private, also set GITHUB_TOKEN (a PAT with repo scope)
#
# HOW TO RUN:
#   Paste this entire script into the HA Web Terminal and press Enter.
#   Or save it as a file and run: bash install_via_web_terminal.sh
# =============================================================================

set -euo pipefail

# ── CONFIGURE THESE ───────────────────────────────────────────────────────────
GITHUB_USER="YOUR_GITHUB_USERNAME"
GITHUB_REPO="YOUR_GITHUB_REPO_NAME"
GITHUB_BRANCH="main"
GITHUB_TOKEN=""   # Leave empty for public repos. For private: "ghp_..."
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL="https://raw.githubusercontent.com/${GITHUB_USER}/${GITHUB_REPO}/${GITHUB_BRANCH}"

if [ -n "$GITHUB_TOKEN" ]; then
  AUTH_HEADER="Authorization: token ${GITHUB_TOKEN}"
else
  AUTH_HEADER=""
fi

download() {
  local url="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [ -n "$AUTH_HEADER" ]; then
    curl -fsSL -H "$AUTH_HEADER" "$url" -o "$dest"
  else
    curl -fsSL "$url" -o "$dest"
  fi
  echo "  ✓ $(basename "$dest")"
}

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     AI Hub — Installing from GitHub onto HA device       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Create directories ────────────────────────────────────────────────────────
echo "▶ Creating directories…"
mkdir -p /config/appdaemon/apps/ai_hub/crews
mkdir -p /config/appdaemon/apps/ai_hub/frontend/dist
mkdir -p /config/appdaemon/logs
echo "  ✓ Directories ready"

# ── AppDaemon config ──────────────────────────────────────────────────────────
echo ""
echo "▶ Downloading AppDaemon config…"
download "${BASE_URL}/appdaemon/appdaemon.yaml" \
         "/config/appdaemon/appdaemon.yaml"

# ── Python app files ──────────────────────────────────────────────────────────
echo ""
echo "▶ Downloading Python modules…"
for f in apps.yaml main.py llm_factory.py crew_router.py agents.py tasks.py tools.py settings_manager.py; do
  download "${BASE_URL}/appdaemon/apps/ai_hub/${f}" \
           "/config/appdaemon/apps/ai_hub/${f}"
done

# ── Crew modules ──────────────────────────────────────────────────────────────
echo ""
echo "▶ Downloading crew modules…"
for f in __init__.py code_review_crew.py ha_automation_crew.py ha_assistant_crew.py; do
  download "${BASE_URL}/appdaemon/apps/ai_hub/crews/${f}" \
           "/config/appdaemon/apps/ai_hub/crews/${f}"
done

# ── Frontend dist files ───────────────────────────────────────────────────────
echo ""
echo "▶ Downloading frontend build…"
# Download the pre-built dist files from the repo
# (You need to commit the dist/ folder to your repo after running npm run build)
DIST_FILES=(
  "index.html"
  "assets/index.css"
  "assets/index.js"
  "assets/react.js"
  "assets/markdown.js"
)

# Try to download dist files — skip gracefully if not committed yet
for f in "${DIST_FILES[@]}"; do
  url="${BASE_URL}/appdaemon/apps/ai_hub/frontend/dist/${f}"
  dest="/config/appdaemon/apps/ai_hub/frontend/dist/${f}"
  mkdir -p "$(dirname "$dest")"
  if curl -fsSL ${AUTH_HEADER:+-H "$AUTH_HEADER"} "$url" -o "$dest" 2>/dev/null; then
    echo "  ✓ dist/${f}"
  else
    echo "  ⚠ dist/${f} not found in repo (commit dist/ after npm run build)"
  fi
done

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Files installed to /config/appdaemon/"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Edit /config/secrets.yaml — add your API keys:"
echo "   nano /config/secrets.yaml"
echo "   (copy entries from ha_config/secrets.yaml.template in the repo)"
echo ""
echo "2. Edit /config/configuration.yaml — add helper entities:"
echo "   nano /config/configuration.yaml"
echo "   (paste contents of ha_config/ai_hub_entities.yaml)"
echo ""
echo "3. Add the sidebar panel to /config/configuration.yaml:"
echo "   panel_iframe:"
echo "     ai_hub:"
echo "       title: \"AI Hub\""
echo "       icon: mdi:robot"
echo "       url: \"http://homeassistant.local:5050/api/appdaemon/ai_hub/\""
echo "       require_admin: true"
echo ""
echo "4. Restart HA: ha core restart"
echo ""
echo "5. Start AppDaemon add-on from the HA UI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
