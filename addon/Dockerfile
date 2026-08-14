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
COPY constraints.txt /app/constraints.txt

# ── Install Python dependencies ───────────────────────────────────────────────
# Strategy to avoid google-re2 (no pre-built musllinux wheel, requires C++):
#
# Step 1: Pre-install google-re2 from the HA wheel index BEFORE anything else.
#         The HA wheel index has a pre-built musllinux aarch64 wheel for it.
#         By installing it first, pip won't try to build it from source later.
#
# Step 2: Install crewai with --no-deps to avoid chromadb/lancedb
#         (which also have no pre-built ARM64 wheels and require Rust).
#
# Step 3: Install all remaining dependencies from requirements.txt.
#         google-re2 is already satisfied from step 1, so pip skips it.

RUN pip install --no-cache-dir \
        --index-url https://wheels.home-assistant.io/musllinux-index/ \
        --extra-index-url https://pypi.org/simple/ \
        "google-re2" \
    && pip install --no-cache-dir \
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
    io.hass.type="addon" \
    io.hass.version="1.0.0"

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["/run.sh"]
