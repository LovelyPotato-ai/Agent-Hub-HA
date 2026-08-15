# =============================================================================
# Dockerfile — AI Hub Add-on
# =============================================================================
# Base image is set by build.yaml per architecture.
# Uses HA's official Python 3.12 Alpine base which includes pre-built wheels
# for ARM64/musl — avoiding Rust compilation failures (chromadb, etc.).
# =============================================================================

ARG BUILD_FROM
FROM ${BUILD_FROM}

# ── System dependencies ───────────────────────────────────────────────────────
RUN apk add --no-cache git libffi-dev musl-dev gcc

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
# CACHE_BUST: v5 — forces rebuild of this layer
ARG CACHE_BUST=v5
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

# ── Install run.sh as an s6-overlay service ───────────────────────────────────
# HA base images use s6-overlay as PID 1 init. The correct pattern is to place
# the entrypoint script at /etc/services.d/<name>/run so s6 manages it.
# Using CMD ["/run.sh"] bypasses s6 and causes:
#   s6-overlay-suexec: fatal: can only run as pid 1
RUN mkdir -p /etc/services.d/ai_hub
COPY run.sh /etc/services.d/ai_hub/run
RUN chmod a+x /etc/services.d/ai_hub/run

# ── Labels ────────────────────────────────────────────────────────────────────
LABEL \
    io.hass.name="AI Hub" \
    io.hass.description="Multi-agent AI orchestrator powered by CrewAI" \
    io.hass.type="addon" \
    io.hass.version="1.0.4"
