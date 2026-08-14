#!/usr/bin/env bash
# =============================================================================
# install.sh — AI Hub deployment script for Home Assistant Green (HAOS)
# =============================================================================
# Run this from your DEVELOPMENT MACHINE (not on the HA device).
# It copies all files to the HA device over SSH and sets up the add-on.
#
# Prerequisites on your dev machine:
#   - SSH access to the HA device (SSH & Web Terminal add-on installed)
#   - scp / ssh available (standard on macOS/Linux; use Git Bash on Windows)
#   - Node.js 20+ (for the frontend build)
#
# Usage:
#   chmod +x install.sh
#   ./install.sh 192.168.1.x        # replace with your HA Green's IP
#   ./install.sh homeassistant.local # or use the hostname
#
# What it does:
#   1. Builds the React frontend (npm run build)
#   2. Creates the target directory structure on the HA device
#   3. Copies all Python files, YAML configs, and the built frontend
#   4. Prints the manual steps you still need to do in the HA UI
# =============================================================================

set -euo pipefail

HA_HOST="${1:-homeassistant.local}"
HA_USER="root"
HA_PORT="${2:-22}"   # Official HA SSH add-on uses port 22 by default
                     # Pass a second argument to override, e.g.: ./install.sh 192.168.1.14 22222
REMOTE_BASE="/config/appdaemon"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          AI Hub — Home Assistant Deployment              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Target: ${HA_USER}@${HA_HOST}:${HA_PORT}"
echo ""

# ── Step 1: Build the frontend ─────────────────────────────────────────────
echo "▶ Step 1/4: Building React frontend…"
cd "${SCRIPT_DIR}/appdaemon/apps/ai_hub/frontend"
npm install --silent
npm run build
echo "  ✓ Frontend built → dist/"
cd "${SCRIPT_DIR}"

# ── Step 2: Create remote directory structure ──────────────────────────────
echo ""
echo "▶ Step 2/4: Creating remote directories…"
ssh -p "${HA_PORT}" "${HA_USER}@${HA_HOST}" "
  mkdir -p ${REMOTE_BASE}/apps/ai_hub/crews
  mkdir -p ${REMOTE_BASE}/apps/ai_hub/frontend/dist
  mkdir -p ${REMOTE_BASE}/logs
  echo '  ✓ Directories created'
"

# ── Step 3: Copy files ─────────────────────────────────────────────────────
echo ""
echo "▶ Step 3/4: Copying files to HA device…"

SCP="scp -P ${HA_PORT}"

# AppDaemon main config
${SCP} "${SCRIPT_DIR}/appdaemon/appdaemon.yaml" \
  "${HA_USER}@${HA_HOST}:${REMOTE_BASE}/appdaemon.yaml"
echo "  ✓ appdaemon.yaml"

# Python app files
for f in main.py llm_factory.py crew_router.py agents.py tasks.py tools.py settings_manager.py; do
  ${SCP} "${SCRIPT_DIR}/appdaemon/apps/ai_hub/${f}" \
    "${HA_USER}@${HA_HOST}:${REMOTE_BASE}/apps/ai_hub/${f}"
done
echo "  ✓ Python modules (main.py, llm_factory.py, crew_router.py, agents.py, tasks.py, tools.py, settings_manager.py)"

# apps.yaml
${SCP} "${SCRIPT_DIR}/appdaemon/apps/ai_hub/apps.yaml" \
  "${HA_USER}@${HA_HOST}:${REMOTE_BASE}/apps/ai_hub/apps.yaml"
echo "  ✓ apps.yaml"

# Crew modules
for f in __init__.py code_review_crew.py ha_automation_crew.py ha_assistant_crew.py; do
  ${SCP} "${SCRIPT_DIR}/appdaemon/apps/ai_hub/crews/${f}" \
    "${HA_USER}@${HA_HOST}:${REMOTE_BASE}/apps/ai_hub/crews/${f}"
done
echo "  ✓ crews/ (3 crew modules)"

# Frontend dist
${SCP} -r "${SCRIPT_DIR}/appdaemon/apps/ai_hub/frontend/dist/." \
  "${HA_USER}@${HA_HOST}:${REMOTE_BASE}/apps/ai_hub/frontend/dist/"
echo "  ✓ frontend/dist/ (React build)"

# ── Step 4: Print manual steps ─────────────────────────────────────────────
echo ""
echo "▶ Step 4/4: Manual steps required in the HA UI"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  A) ADD SECRETS to /config/secrets.yaml"
echo "     (Settings → System → Edit secrets.yaml in File Editor)"
echo ""
echo "     Copy from: ha_config/secrets.yaml.template"
echo "     Fill in:   appdaemon_token, active_llm_provider,"
echo "                active_llm_model, your API key(s),"
echo "                github_pat, github_repo_owner, github_repo_name"
echo ""
echo "  B) ADD HELPER ENTITIES to /config/configuration.yaml"
echo "     Paste the contents of ha_config/ai_hub_entities.yaml"
echo "     under the input_text: and input_button: sections."
echo ""
echo "  C) ADD AUTOMATIONS"
echo "     In HA → Settings → Automations, import or paste"
echo "     the automations from ha_config/automations.yaml"
echo ""
echo "  D) ADD SIDEBAR PANEL to /config/configuration.yaml"
echo ""
echo "     panel_iframe:"
echo "       ai_hub:"
echo "         title: \"AI Hub\""
echo "         icon: mdi:robot"
echo "         url: \"http://${HA_HOST}:5050/api/appdaemon/ai_hub/\""
echo "         require_admin: true"
echo ""
echo "  E) INSTALL AppDaemon add-on (if not already installed)"
echo "     Settings → Add-ons → Add-on Store → search 'AppDaemon'"
echo "     Install 'AppDaemon 4' by AppDaemon"
echo ""
echo "  F) RESTART"
echo "     1. Restart Home Assistant (Developer Tools → Restart)"
echo "     2. Start / Restart the AppDaemon add-on"
echo ""
echo "  G) VERIFY in AppDaemon add-on logs:"
echo "     'AI Hub Orchestrator ready.'"
echo "     'HTTP endpoints registered at /api/appdaemon/ai_hub/'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ File deployment complete!"
echo "   Open the AI Hub at: http://${HA_HOST}:5050/api/appdaemon/ai_hub/"
echo "   (or via the HA sidebar after step D + restart)"
echo ""
