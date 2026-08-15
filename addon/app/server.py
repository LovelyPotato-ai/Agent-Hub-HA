"""
server.py — AI Hub Standalone aiohttp Server
=============================================
Main entry point for the custom HA add-on.

Replaces AppDaemon's built-in HTTP server. Runs as the main process,
started by run.sh.

Responsibilities:
  - Start the HAClient (connects to HA Supervisor WebSocket)
  - Start the AIHubOrchestrator (subscribes to HA events)
  - Serve the React frontend as static files at /
  - Expose REST + WebSocket API endpoints at /api/
  - Handle graceful shutdown on SIGTERM/SIGINT
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path

from aiohttp import web

from ha_client import HAClient
from orchestrator import AIHubOrchestrator

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("AI_HUB_LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ai_hub.server")

# ---------------------------------------------------------------------------
# Static file directory
# ---------------------------------------------------------------------------

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

@web.middleware
async def _cors_middleware(request: web.Request, handler):
    """Allow all origins — needed for local dev (npm run dev proxy)."""
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def build_app(orchestrator: AIHubOrchestrator) -> web.Application:
    """
    Build the aiohttp Application with all routes registered.
    """
    # Middlewares must be passed at construction time — cannot be appended after.
    app = web.Application(middlewares=[_cors_middleware])

    # ── API routes ─────────────────────────────────────────────────────
    app.router.add_post("/api/trigger",          orchestrator.http_trigger)
    app.router.add_get("/api/status",            orchestrator.http_status)
    app.router.add_get("/api/result",            orchestrator.http_result)
    app.router.add_get("/api/ws",                orchestrator.http_ws)
    app.router.add_get("/api/settings",          orchestrator.http_settings_get)
    app.router.add_post("/api/settings/save",    orchestrator.http_settings_post)
    app.router.add_get("/api/settings/metadata", orchestrator.http_settings_metadata)

    # ── Health check ───────────────────────────────────────────────────
    app.router.add_get("/api/health", _health_check)

    # ── Static frontend files ──────────────────────────────────────────
    if FRONTEND_DIST.exists():
        # Serve index.html for the root path
        app.router.add_get("/", _serve_index)
        # Serve all other static assets
        app.router.add_static("/assets", FRONTEND_DIST / "assets", name="assets")
        logger.info("Serving frontend from %s", FRONTEND_DIST)
    else:
        app.router.add_get("/", _no_frontend)
        logger.warning(
            "Frontend dist/ not found at %s. "
            "Run 'npm run build' in the frontend/ directory and copy dist/ here.",
            FRONTEND_DIST,
        )

    return app


async def _health_check(request: web.Request) -> web.Response:
    return web.Response(
        text=json.dumps({"status": "ok", "service": "ai_hub"}),
        content_type="application/json",
    )


async def _serve_index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(FRONTEND_DIST / "index.html")


async def _no_frontend(request: web.Request) -> web.Response:
    return web.Response(
        text=json.dumps({
            "status": "running",
            "message": "AI Hub API is running. Frontend not built yet.",
            "api_docs": "/api/health",
        }),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    port = int(os.environ.get("AI_HUB_PORT", "8099"))

    # ── Connect to HA ──────────────────────────────────────────────────
    ha_client = None
    try:
        ha_client = HAClient()
        await ha_client.connect()
    except Exception as exc:
        logger.error("Failed to connect to HA Supervisor: %s", exc)
        logger.error("Continuing without HA connection — entity updates will fail.")
        ha_client = None  # type: ignore[assignment]

    # ── Start orchestrator ─────────────────────────────────────────────
    orchestrator = AIHubOrchestrator(ha_client=ha_client)
    await orchestrator.start()

    # ── Build and start HTTP server ────────────────────────────────────
    app = build_app(orchestrator)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("AI Hub server started on http://0.0.0.0:%d", port)
    logger.info("API available at http://0.0.0.0:%d/api/", port)

    # ── Graceful shutdown ──────────────────────────────────────────────
    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    await stop_event.wait()

    logger.info("Shutting down AI Hub...")
    await runner.cleanup()
    if ha_client:
        await ha_client.close()
    logger.info("AI Hub stopped.")


if __name__ == "__main__":
    asyncio.run(main())
