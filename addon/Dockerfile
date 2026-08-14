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
# google-re2 has NO pre-built musllinux wheel and requires C++ compilation.
# It is pulled in by google-generativeai (old SDK).
# langchain-google-genai 4.x uses google-genai (new SDK) which does NOT
# require google-re2. We install langchain-google-genai with --no-deps
# to skip google-generativeai entirely, then install google-genai directly.
#
# crewai is installed with --no-deps to avoid chromadb/lancedb (Rust builds).

RUN pip install --no-cache-dir \
        --extra-index-url https://wheels.home-assistant.io/musllinux-index/ \
        --no-deps \
        "crewai==1.15.16" \
        "langchain-google-genai>=4.0.0" \
    && pip install --no-cache-dir \
        --extra-index-url https://wheels.home-assistant.io/musllinux-index/ \
        "google-genai>=1.0.0" \
    && pip install --no-cache-dir \
        --extra-index-url https://wheels.home-assistant.io/musllinux-index/ \
        -r /app/requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY app/ /app/
COPY run.sh /run.sh
RUN chmod +x /run.sh

# ── Labels ────────────────────────────────────────────────────────────────────
LABEL \
    io.hass.name="AI Hub" \
    io.hass.description="Multi-agent AI orchestrator powered by CrewAI" \
    io.hass.type="addon" \
    io.hass.version="1.0.0"

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["/run.sh"]
