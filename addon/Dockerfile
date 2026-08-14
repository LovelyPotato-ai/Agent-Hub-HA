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
# git: required by some pip packages during install
# g++, gcc, libffi-dev, musl-dev: needed for native extension builds on Alpine
# re2-dev: provides the C++ re2 library needed by google-re2
RUN apk add --no-cache \
    git \
    gcc \
    g++ \
    libffi-dev \
    musl-dev \
    re2-dev \
    make

# ── Copy requirements first (layer cache optimisation) ────────────────────────
WORKDIR /app
COPY requirements.txt /app/requirements.txt

# ── Install Python dependencies ───────────────────────────────────────────────
# Use HA's pre-built wheel index for fast ARM64 installs.
# Install crewai with --no-deps first to avoid chromadb/lancedb (ARM64 build failures).
# Then install crewai's actual runtime deps manually.
RUN pip install --no-cache-dir \
    --extra-index-url https://wheels.home-assistant.io/musllinux-index/ \
    --no-deps \
    "crewai==1.15.16" \
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
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="1.0.0"

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["/run.sh"]
