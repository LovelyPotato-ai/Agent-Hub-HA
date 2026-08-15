# =============================================================================
# Dockerfile — AI Hub Add-on
# =============================================================================
# Base image is set by build.yaml per architecture.
# Uses HA's official Python 3.12 Alpine base which includes pre-built wheels
# for ARM64/musl — avoiding Rust compilation failures (chromadb, etc.).
# =============================================================================

ARG BUILD_FROM
FROM ${BUILD_FROM}

# ── Force full rebuild (invalidates ALL subsequent layers) ───────────────────
# Increment this value to bust the entire Docker layer cache on next build.
# CACHE_BUST: v10
ARG CACHE_BUST=v10
RUN echo "Cache bust: ${CACHE_BUST}"

# ── System dependencies ───────────────────────────────────────────────────────
# jq   — required by run.sh to parse /data/options.json without bashio/with-contenv
# nodejs/npm — required to build the React frontend during image build
RUN apk add --no-cache git libffi-dev musl-dev gcc jq nodejs npm

# ── Copy requirements first (layer cache optimisation) ────────────────────────
WORKDIR /app
COPY requirements.txt /app/requirements.txt

# ── Install Python dependencies ───────────────────────────────────────────────
# google-re2 has NO pre-built musllinux wheel — it only exists as a source
# distribution requiring C++ compilation (g++). It is pulled in by
# google-generativeai (old SDK). We avoid it by:
#
# 1. Installing langchain-google-genai with --no-deps (skips google-generativeai)
# 2. Installing google-genai directly (new SDK, no google-re2 dependency)
# 3. Installing crewai with --no-deps (avoids chromadb/lancedb Rust builds)
# 4. Installing all remaining deps from requirements.txt
#
RUN pip install --no-cache-dir \
        --extra-index-url https://wheels.home-assistant.io/musllinux-index/ \
        --no-deps \
        "crewai==1.15.16" \
        "langchain-google-genai>=4.0.0" \
        "cel-python>=0.5.0,<0.6" \
    && pip install --no-cache-dir \
        --extra-index-url https://wheels.home-assistant.io/musllinux-index/ \
        "google-genai>=1.0.0" \
    && pip install --no-cache-dir \
        --extra-index-url https://wheels.home-assistant.io/musllinux-index/ \
        -r /app/requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY app/ /app/

# ── Build React frontend ──────────────────────────────────────────────────────
# Frontend source is in /app/frontend/ (copied above).
# npm ci installs deps, npm run build outputs to /app/frontend/dist/,
# then node_modules is removed to keep the image lean.
# The server.py looks for frontend/dist/ relative to its own location (/app/).
RUN cd /app/frontend \
    && npm ci \
    && npm run build \
    && rm -rf node_modules

# ── Install run.sh as an s6-overlay v3 service ───────────────────────────────
# HA base images use s6-overlay v3. The v3 service directory structure is:
#   /etc/s6-overlay/s6-rc.d/<name>/type       — contains "longrun"
#   /etc/s6-overlay/s6-rc.d/<name>/run        — the service script
#   /etc/s6-overlay/s6-rc.d/user/contents.d/<name> — enables the service
# The old v2 path /etc/services.d/ does NOT work with v3.
RUN mkdir -p /etc/s6-overlay/s6-rc.d/ai_hub \
    && echo "longrun" > /etc/s6-overlay/s6-rc.d/ai_hub/type \
    && mkdir -p /etc/s6-overlay/s6-rc.d/user/contents.d \
    && touch /etc/s6-overlay/s6-rc.d/user/contents.d/ai_hub
COPY run.sh /etc/s6-overlay/s6-rc.d/ai_hub/run
RUN chmod a+x /etc/s6-overlay/s6-rc.d/ai_hub/run

# ── Labels ────────────────────────────────────────────────────────────────────
LABEL \
    io.hass.name="AI Hub" \
    io.hass.description="Multi-agent AI orchestrator powered by CrewAI" \
    io.hass.type="addon" \
    io.hass.version="1.1.0"
