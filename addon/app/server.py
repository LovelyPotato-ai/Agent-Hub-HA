"""
server.py — AI Hub Standalone aiohttp Server
=============================================
Main entry point for the custom HA add-on.

Responsibilities:
  - Start the HAClient (connects to HA Supervisor WebSocket)
  - Start the AIHubOrchestrator (seeds defaults, inits LLM + tools)
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
# CORS middleware
# ---------------------------------------------------------------------------

@web.middleware
async def _cors_middleware(request: web.Request, handler):
    """Allow all origins — needed for local dev (npm run dev proxy)."""
    # Handle CORS preflight before routing so OPTIONS never hits a 405.
    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Max-Age": "86400",
            },
        )
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


# ---------------------------------------------------------------------------
# Static file handlers
# ---------------------------------------------------------------------------

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


async def _health_check(request: web.Request) -> web.Response:
    return web.Response(
        text=json.dumps({"status": "ok", "service": "ai_hub"}),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def build_app(orchestrator: AIHubOrchestrator) -> web.Application:
    """Build the aiohttp Application with all routes registered."""
    app = web.Application(middlewares=[_cors_middleware])

    # ── Health check ───────────────────────────────────────────────────
    app.router.add_get("/api/health", _health_check)

    # ── Agent CRUD ─────────────────────────────────────────────────────
    app.router.add_get("/api/agents",          orchestrator.http_agents_list)
    app.router.add_post("/api/agents",         orchestrator.http_agents_create)
    app.router.add_get("/api/agents/{id}",     orchestrator.http_agents_get)
    app.router.add_put("/api/agents/{id}",     orchestrator.http_agents_update)
    app.router.add_delete("/api/agents/{id}",  orchestrator.http_agents_delete)

    # ── Workflow CRUD ──────────────────────────────────────────────────
    app.router.add_get("/api/workflows",           orchestrator.http_workflows_list)
    app.router.add_post("/api/workflows",          orchestrator.http_workflows_create)
    app.router.add_get("/api/workflows/{id}",      orchestrator.http_workflows_get)
    app.router.add_put("/api/workflows/{id}",      orchestrator.http_workflows_update)
    app.router.add_delete("/api/workflows/{id}",   orchestrator.http_workflows_delete)

    # ── Providers ──────────────────────────────────────────────────────
    app.router.add_get("/api/providers",          orchestrator.http_providers_list)
    app.router.add_post("/api/providers",         orchestrator.http_providers_create)
    app.router.add_put("/api/providers/{id}",     orchestrator.http_providers_update)
    app.router.add_delete("/api/providers/{id}",  orchestrator.http_providers_delete)

    # ── Tools ──────────────────────────────────────────────────────────
    app.router.add_get("/api/tools", orchestrator.http_tools_list)

    # ── Run endpoints ──────────────────────────────────────────────────
    app.router.add_post("/api/run/workflow/{id}", orchestrator.http_run_workflow)
    app.router.add_post("/api/run/agent/{id}",    orchestrator.http_run_agent)

    # ── Legacy / status / WebSocket ────────────────────────────────────
    app.router.add_post("/api/trigger",           orchestrator.http_trigger)
    app.router.add_get("/api/status",             orchestrator.http_status)
    app.router.add_get("/api/result",             orchestrator.http_result)
    app.router.add_get("/api/ws",                 orchestrator.http_ws)

    # ── Settings ───────────────────────────────────────────────────────
    app.router.add_get("/api/settings",           orchestrator.http_settings_get)
    app.router.add_post("/api/settings/save",     orchestrator.http_settings_post)
    app.router.add_get("/api/settings/metadata",  orchestrator.http_settings_metadata)

    # ── Static frontend files ──────────────────────────────────────────
    if FRONTEND_DIST.exists():
        app.router.add_get("/", _serve_index)
        app.router.add_static("/assets", FRONTEND_DIST / "assets", name="assets")
        # Catch-all: serve index.html for any non-API GET (SPA routing + HA Ingress)
        app.router.add_route("GET", "/{path_info:.*}", _serve_index)
        logger.info("Serving frontend from %s", FRONTEND_DIST)
    else:
        app.router.add_get("/", _no_frontend)
        app.router.add_route("GET", "/{path_info:.*}", _no_frontend)
        logger.warning(
            "Frontend dist/ not found at %s. "
            "Run 'npm run build' in the frontend/ directory.",
            FRONTEND_DIST,
        )

    return app


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
    await orchestrator.stop()
    await runner.cleanup()
    if ha_client:
        await ha_client.close()
    logger.info("AI Hub stopped.")


if __name__ == "__main__":
    asyncio.run(main())
