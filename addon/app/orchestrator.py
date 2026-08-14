"""
orchestrator.py — AI Hub Orchestrator
=======================================
Standalone replacement for the AppDaemon-based main.py.

Bridges the HA event bus (via HAClient) with the CrewAI multi-agent system.
Exposes aiohttp request handlers that are registered by server.py.

Key differences from the AppDaemon version:
  - No hass.Hass inheritance — uses HAClient directly
  - Configuration read from environment variables (set by run.sh from add-on options)
  - run_in_executor uses asyncio's default thread pool
  - WebSocket broadcast uses asyncio.run_coroutine_threadsafe
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from aiohttp import web

from crew_router import route as route_crew
from ha_client import HAClient
from llm_factory import get_llm
from settings_manager import get_metadata, load_settings, save_settings
from tools import GitHubCommitTool, HASensorReaderTool

logger = logging.getLogger("ai_hub.orchestrator")

# ---------------------------------------------------------------------------
# HA entity IDs (virtual entities written via REST API)
# ---------------------------------------------------------------------------
ENTITY_STATUS      = "input_text.ai_hub_status"
ENTITY_RESULT      = "input_text.ai_hub_result"
ENTITY_ACTIVE_CREW = "input_text.ai_hub_active_crew"
ENTITY_ERROR       = "input_text.ai_hub_error"
TRIGGER_EVENT      = "ai_hub_trigger"


class AIHubOrchestrator:
    """
    Standalone AI Hub orchestrator.

    Lifecycle:
      await orchestrator.start()   — connect to HA, subscribe to events, init LLM
      await orchestrator.stop()    — clean up thread pool
    """

    def __init__(self, ha_client: HAClient | None) -> None:
        self._ha = ha_client
        self._ws_clients: dict[str, set] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=3,
            thread_name_prefix="ai_hub_crew",
        )
        self._llm: Any = None
        self._github_tool: GitHubCommitTool | None = None
        self._ha_sensor_tool: HASensorReaderTool | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialise LLM, tools, and subscribe to HA events."""
        logger.info("AI Hub Orchestrator starting…")

        # ── LLM factory ────────────────────────────────────────────────
        provider = os.environ.get("AI_HUB_LLM_PROVIDER", "openai")
        model    = os.environ.get("AI_HUB_LLM_MODEL", "gpt-4o")
        api_keys = {
            "openai":     os.environ.get("AI_HUB_OPENAI_KEY", ""),
            "gemini":     os.environ.get("AI_HUB_GEMINI_KEY", ""),
            "anthropic":  os.environ.get("AI_HUB_ANTHROPIC_KEY", ""),
            "openrouter": os.environ.get("AI_HUB_OPENROUTER_KEY", ""),
        }

        try:
            self._llm = get_llm(
                provider=provider,
                model=model,
                api_key=api_keys.get(provider, ""),
            )
            logger.info("LLM initialised: provider=%s, model=%s", provider, model)
        except ValueError as exc:
            logger.error("LLM factory error: %s", exc)
            await self._set_status("error")
            await self._set_error(str(exc))
            # Don't return — server still starts, user can fix via Settings tab

        # ── Tools ──────────────────────────────────────────────────────
        self._github_tool = GitHubCommitTool(
            pat=os.environ.get("AI_HUB_GITHUB_PAT", ""),
            owner=os.environ.get("AI_HUB_GITHUB_OWNER", ""),
            repo=os.environ.get("AI_HUB_GITHUB_REPO", ""),
            branch=os.environ.get("AI_HUB_GITHUB_BRANCH", "main"),
        )
        self._ha_sensor_tool = HASensorReaderTool(ha_client=self._ha)

        # ── Subscribe to HA trigger event ──────────────────────────────
        if self._ha:
            await self._ha.subscribe_events(TRIGGER_EVENT, self._on_trigger)
            logger.info("Subscribed to HA event: '%s'", TRIGGER_EVENT)

        await self._set_status("idle")
        logger.info("AI Hub Orchestrator ready.")

    async def stop(self) -> None:
        """Shut down the thread pool."""
        self._executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # HA Event Handler
    # ------------------------------------------------------------------

    async def _on_trigger(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Called when the 'ai_hub_trigger' HA event fires.
        Validates the payload and dispatches crew execution to a thread.
        """
        logger.info("Received trigger event: %s", data)

        crew_name = data.get("crew", "").strip()
        prompt    = data.get("prompt", "").strip()

        if not crew_name:
            await self._report_error("Trigger payload missing 'crew' field.")
            return
        if not prompt:
            await self._report_error("Trigger payload missing 'prompt' field.")
            return

        job_id = str(uuid.uuid4())[:8]
        logger.info("Starting job %s: crew=%s", job_id, crew_name)

        await self._set_status("running")
        if self._ha:
            await self._ha.set_state(ENTITY_ACTIVE_CREW, crew_name)
            await self._ha.set_state(ENTITY_ERROR, "")

        # Dispatch to thread pool (non-blocking)
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            self._executor,
            self._run_crew_sync,
            job_id,
            crew_name,
            prompt,
            data.get("options", {}),
        )

    # ------------------------------------------------------------------
    # Crew Execution (runs in thread pool)
    # ------------------------------------------------------------------

    def _run_crew_sync(
        self,
        job_id: str,
        crew_name: str,
        prompt: str,
        options: dict[str, Any],
    ) -> None:
        """
        Blocking function executed in a worker thread.
        Calls crew_router.route() → crew.kickoff().
        Reports result/error back to the async event loop.
        """
        logger.info("[%s] Crew '%s' kickoff starting…", job_id, crew_name)
        start_ts = datetime.utcnow()

        try:
            result: str = route_crew(
                payload={"crew": crew_name, "prompt": prompt, "options": options},
                llm=self._llm,
                tools={
                    "github_tool":    self._github_tool,
                    "ha_sensor_tool": self._ha_sensor_tool,
                },
            )
            elapsed = (datetime.utcnow() - start_ts).total_seconds()
            logger.info("[%s] Crew '%s' finished in %.1fs.", job_id, crew_name, elapsed)

            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self._report_result(job_id, crew_name, result),
                loop,
            )

        except ValueError as exc:
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self._report_error(str(exc), job_id=job_id),
                loop,
            )
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            logger.error("[%s] Unexpected error:\n%s", job_id, tb)
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self._report_error(
                    f"[{crew_name}] {type(exc).__name__}: {exc}",
                    job_id=job_id,
                ),
                loop,
            )

    # ------------------------------------------------------------------
    # Result & Error Reporting
    # ------------------------------------------------------------------

    async def _report_result(self, job_id: str, crew_name: str, result: str) -> None:
        truncated = result[:252] + "…" if len(result) > 255 else result
        await self._set_status("done")
        if self._ha:
            await self._ha.set_state(ENTITY_RESULT, truncated)
            await self._ha.persistent_notification(
                title=f"AI Hub — {crew_name} finished",
                message=truncated,
            )
        self._ws_broadcast(job_id, {
            "type": "result",
            "job_id": job_id,
            "crew": crew_name,
            "status": "done",
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info("[%s] Result reported.", job_id)

    async def _report_error(self, message: str, job_id: str = "") -> None:
        await self._set_status("error")
        if self._ha:
            await self._ha.set_state(ENTITY_ERROR, message[:255])
            await self._ha.fire_event("ai_hub_error", message=message, job_id=job_id)
            await self._ha.persistent_notification(title="AI Hub — Error", message=message)
        if job_id:
            self._ws_broadcast(job_id, {
                "type": "error",
                "job_id": job_id,
                "status": "error",
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            })
        logger.error("Error reported: %s", message)

    async def _set_status(self, status: str) -> None:
        if self._ha:
            try:
                await self._ha.set_state(ENTITY_STATUS, status)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to set HA status entity: %s", exc)

    async def _set_error(self, message: str) -> None:
        if self._ha:
            try:
                await self._ha.set_state(ENTITY_ERROR, message[:255])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to set HA error entity: %s", exc)

    # ------------------------------------------------------------------
    # WebSocket Broadcast
    # ------------------------------------------------------------------

    def _ws_broadcast(self, job_id: str, payload: dict[str, Any]) -> None:
        """Push JSON to all WebSocket clients for job_id and the global '*' channel."""
        clients = self._ws_clients.get(job_id, set()).copy()
        clients |= self._ws_clients.get("*", set()).copy()
        if not clients:
            return
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(
            self._ws_send_all(clients, payload),
            loop,
        )

    async def _ws_send_all(self, clients: set, payload: dict[str, Any]) -> None:
        message = json.dumps(payload)
        dead: set = set()
        for ws in clients:
            try:
                await ws.send_str(message)
            except Exception:  # noqa: BLE001
                dead.add(ws)
        for job_clients in self._ws_clients.values():
            job_clients -= dead

    # ------------------------------------------------------------------
    # HTTP Request Handlers (registered by server.py)
    # ------------------------------------------------------------------

    async def http_trigger(self, request: web.Request) -> web.Response:
        """POST /api/trigger — start a crew run."""
        try:
            body = await request.json()
        except Exception:
            return web.Response(
                status=400,
                text=json.dumps({"error": "Invalid JSON body"}),
                content_type="application/json",
            )

        crew_name = body.get("crew", "").strip()
        prompt    = body.get("prompt", "").strip()

        if not crew_name or not prompt:
            return web.Response(
                status=422,
                text=json.dumps({"error": "'crew' and 'prompt' are required"}),
                content_type="application/json",
            )

        job_id = str(uuid.uuid4())[:8]

        if self._ha:
            await self._ha.fire_event(
                TRIGGER_EVENT,
                crew=crew_name,
                prompt=prompt,
                options=body.get("options", {}),
                job_id=job_id,
            )
        else:
            # No HA connection — trigger directly
            await self._on_trigger(TRIGGER_EVENT, {
                "crew": crew_name,
                "prompt": prompt,
                "options": body.get("options", {}),
                "job_id": job_id,
            })

        return web.Response(
            status=202,
            text=json.dumps({"job_id": job_id, "status": "accepted"}),
            content_type="application/json",
        )

    async def http_status(self, request: web.Request) -> web.Response:
        """GET /api/status — current hub status."""
        status = "idle"
        active_crew = ""
        if self._ha:
            status = await self._ha.get_state(ENTITY_STATUS) or "idle"
            active_crew = await self._ha.get_state(ENTITY_ACTIVE_CREW) or ""
        return web.Response(
            text=json.dumps({"status": status, "active_crew": active_crew}),
            content_type="application/json",
        )

    async def http_result(self, request: web.Request) -> web.Response:
        """GET /api/result — last result and error."""
        result = ""
        error  = ""
        if self._ha:
            result = await self._ha.get_state(ENTITY_RESULT) or ""
            error  = await self._ha.get_state(ENTITY_ERROR) or ""
        return web.Response(
            text=json.dumps({"result": result, "error": error}),
            content_type="application/json",
        )

    async def http_ws(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket /api/ws?job_id=<id> — real-time status/result push."""
        job_id = request.rel_url.query.get("job_id", "*")
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._ws_clients.setdefault(job_id, set()).add(ws)
        logger.debug("WebSocket client connected (job_id=%s)", job_id)

        # Send current status immediately
        status = "idle"
        active_crew = ""
        if self._ha:
            status = await self._ha.get_state(ENTITY_STATUS) or "idle"
            active_crew = await self._ha.get_state(ENTITY_ACTIVE_CREW) or ""
        await ws.send_str(json.dumps({
            "type": "status",
            "status": status,
            "active_crew": active_crew,
        }))

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            self._ws_clients.get(job_id, set()).discard(ws)
            logger.debug("WebSocket client disconnected (job_id=%s)", job_id)

        return ws

    async def http_settings_get(self, request: web.Request) -> web.Response:
        """GET /api/settings — load current settings."""
        try:
            settings = await asyncio.get_event_loop().run_in_executor(
                None, load_settings
            )
            return web.Response(
                text=json.dumps(settings),
                content_type="application/json",
            )
        except Exception as exc:  # noqa: BLE001
            return web.Response(
                status=500,
                text=json.dumps({"error": str(exc)}),
                content_type="application/json",
            )

    async def http_settings_post(self, request: web.Request) -> web.Response:
        """POST /api/settings/save — persist settings."""
        try:
            body = await request.json()
        except Exception:
            return web.Response(
                status=400,
                text=json.dumps({"error": "Invalid JSON body"}),
                content_type="application/json",
            )
        result = await asyncio.get_event_loop().run_in_executor(
            None, save_settings, body
        )
        status_code = 200 if result.get("status") == "ok" else 500
        return web.Response(
            status=status_code,
            text=json.dumps(result),
            content_type="application/json",
        )

    async def http_settings_metadata(self, request: web.Request) -> web.Response:
        """GET /api/settings/metadata — agent roles + provider model lists."""
        try:
            metadata = await asyncio.get_event_loop().run_in_executor(
                None, get_metadata
            )
            return web.Response(
                text=json.dumps(metadata),
                content_type="application/json",
            )
        except Exception as exc:  # noqa: BLE001
            return web.Response(
                status=500,
                text=json.dumps({"error": str(exc)}),
                content_type="application/json",
            )
