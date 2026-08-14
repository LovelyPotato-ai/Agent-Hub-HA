"""
main.py — AIHubOrchestrator
============================
AppDaemon application that bridges Home Assistant's event bus with the
CrewAI multi-agent system.

Responsibilities:
  - Listen for the 'ai_hub_trigger' HA event
  - Validate the incoming payload
  - Dispatch crew execution to a thread pool (non-blocking)
  - Report status, results, and errors back to HA entities
  - Expose aiohttp REST + WebSocket endpoints for the React frontend

Deploy to: /config/appdaemon/apps/ai_hub/main.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import appdaemon.plugins.hass.hassapi as hass
from aiohttp import web

from crew_router import route as route_crew
from llm_factory import get_llm
from settings_manager import get_metadata, load_settings, save_settings
from tools import GitHubCommitTool, HASensorReaderTool

# ---------------------------------------------------------------------------
# Module-level logger (writes to the ai_hub_log defined in appdaemon.yaml)
# ---------------------------------------------------------------------------
logger = logging.getLogger("ai_hub")


class AIHubOrchestrator(hass.Hass):
    """
    Main AppDaemon application class.

    Inherits from hass.Hass which provides:
      - self.listen_event()   — subscribe to HA events
      - self.set_state()      — write to HA entity states
      - self.get_state()      — read HA entity states
      - self.call_service()   — call any HA service
      - self.fire_event()     — fire custom HA events
      - self.run_in_executor()— offload blocking work to a thread pool
      - self.log()            — write to AppDaemon logs
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        Called once by AppDaemon when the app starts.
        Reads configuration from self.args (injected from apps.yaml),
        builds shared resources, registers event listeners, and
        registers HTTP endpoints.
        """
        self.log("AI Hub Orchestrator initialising…", level="INFO")

        # ── Configuration from apps.yaml / secrets.yaml ────────────────
        self._trigger_event: str = self.args.get("trigger_event", "ai_hub_trigger")
        self._result_entity: str = self.args.get("result_entity", "input_text.ai_hub_result")
        self._status_entity: str = self.args.get("status_entity", "input_text.ai_hub_status")
        self._active_crew_entity: str = "input_text.ai_hub_active_crew"
        self._error_entity: str = "input_text.ai_hub_error"

        # ── LLM factory ────────────────────────────────────────────────
        provider: str = self.args["active_llm_provider"]
        model: str = self.args["active_llm_model"]
        api_keys: dict[str, str] = {
            "openai": self.args.get("openai_api_key", ""),
            "gemini": self.args.get("gemini_api_key", ""),
            "anthropic": self.args.get("anthropic_api_key", ""),
            "openrouter": self.args.get("openrouter_api_key", ""),
        }

        try:
            self._llm = get_llm(
                provider=provider,
                model=model,
                api_key=api_keys.get(provider, ""),
            )
            self.log(f"LLM initialised: provider={provider}, model={model}", level="INFO")
        except ValueError as exc:
            self.log(f"LLM factory error: {exc}", level="ERROR")
            self._set_status("error")
            self._set_error(str(exc))
            return

        # ── Shared tools (constructed once, reused across crews) ───────
        self._github_tool = GitHubCommitTool(
            pat=self.args.get("github_pat", ""),
            owner=self.args.get("github_repo_owner", ""),
            repo=self.args.get("github_repo_name", ""),
            branch=self.args.get("github_branch", "main"),
        )
        self._ha_sensor_tool = HASensorReaderTool(hass_app=self)

        # ── Thread pool for blocking crew.kickoff() calls ──────────────
        # AppDaemon's built-in executor is used via self.run_in_executor,
        # but we keep a reference for explicit use if needed.
        self._executor = ThreadPoolExecutor(
            max_workers=3,
            thread_name_prefix="ai_hub_crew",
        )

        # ── WebSocket client registry ──────────────────────────────────
        # Maps job_id → set of aiohttp WebSocketResponse objects
        self._ws_clients: dict[str, set] = {}

        # ── Register HA event listener ─────────────────────────────────
        self.listen_event(self._on_trigger, self._trigger_event)
        self.log(f"Listening for HA event: '{self._trigger_event}'", level="INFO")

        # ── Register aiohttp HTTP endpoints ───────────────────────────
        self._register_http_endpoints()

        # ── Set initial status ─────────────────────────────────────────
        self._set_status("idle")
        self.log("AI Hub Orchestrator ready.", level="INFO")

    # ------------------------------------------------------------------
    # HA Event Handler
    # ------------------------------------------------------------------

    def _on_trigger(
        self,
        event_name: str,
        data: dict[str, Any],
        kwargs: dict[str, Any],
    ) -> None:
        """
        Called by AppDaemon when the 'ai_hub_trigger' event fires.
        Validates the payload and dispatches crew execution to a thread.
        """
        self.log(f"Received trigger event: {data}", level="INFO")

        # ── Validate payload ───────────────────────────────────────────
        crew_name = data.get("crew")
        prompt = data.get("prompt", "").strip()

        if not crew_name:
            self._report_error("Trigger payload missing 'crew' field.")
            return
        if not prompt:
            self._report_error("Trigger payload missing 'prompt' field.")
            return

        # ── Generate a unique job ID for this run ──────────────────────
        job_id = str(uuid.uuid4())[:8]
        self.log(f"Starting job {job_id}: crew={crew_name}", level="INFO")

        # ── Update HA entities ─────────────────────────────────────────
        self._set_status("running")
        self.set_state(self._active_crew_entity, state=crew_name)
        self.set_state(self._error_entity, state="")

        # ── Dispatch to thread pool (non-blocking) ─────────────────────
        # run_in_executor schedules _run_crew_sync on AppDaemon's thread
        # pool and returns immediately, keeping the event loop free.
        self.run_in_executor(
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
        Calls crew_router.route() which calls crew.kickoff() internally.
        Reports result or error back to the HA event loop via
        self.call_soon_threadsafe (wrapped by AppDaemon's thread-safe
        set_state / fire_event calls).
        """
        self.log(f"[{job_id}] Crew '{crew_name}' kickoff starting…", level="INFO")
        start_ts = datetime.utcnow()

        try:
            result: str = route_crew(
                payload={
                    "crew": crew_name,
                    "prompt": prompt,
                    "options": options,
                },
                llm=self._llm,
                tools={
                    "github_tool": self._github_tool,
                    "ha_sensor_tool": self._ha_sensor_tool,
                },
            )

            elapsed = (datetime.utcnow() - start_ts).total_seconds()
            self.log(
                f"[{job_id}] Crew '{crew_name}' finished in {elapsed:.1f}s.",
                level="INFO",
            )
            self._report_result(job_id, crew_name, result)

        except ValueError as exc:
            # Invalid crew name or configuration error
            self.log(f"[{job_id}] Configuration error: {exc}", level="ERROR")
            self._report_error(str(exc), job_id=job_id)

        except Exception as exc:  # noqa: BLE001
            # Catch-all: API timeouts, GitHub errors, CrewAI internals
            tb = traceback.format_exc()
            self.log(f"[{job_id}] Unexpected error:\n{tb}", level="ERROR")
            self._report_error(
                f"[{crew_name}] {type(exc).__name__}: {exc}",
                job_id=job_id,
            )

    # ------------------------------------------------------------------
    # Result & Error Reporting
    # ------------------------------------------------------------------

    def _report_result(self, job_id: str, crew_name: str, result: str) -> None:
        """Write the crew result back to HA entities and push via WebSocket."""
        # Truncate for the input_text entity (255 char limit)
        truncated = result[:252] + "…" if len(result) > 255 else result

        self._set_status("done")
        self.set_state(self._result_entity, state=truncated)

        # Persistent HA notification
        self._notify(
            title=f"AI Hub — {crew_name} finished",
            message=truncated,
        )

        # Push full result to all WebSocket clients for this job
        self._ws_broadcast(
            job_id=job_id,
            payload={
                "type": "result",
                "job_id": job_id,
                "crew": crew_name,
                "status": "done",
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        self.log(f"[{job_id}] Result reported to HA.", level="INFO")

    def _report_error(self, message: str, job_id: str = "") -> None:
        """Write an error to HA entities, fire an error event, and push via WS."""
        self._set_status("error")
        self.set_state(self._error_entity, state=message[:255])

        # Fire a custom HA event so automations can react
        self.fire_event("ai_hub_error", message=message, job_id=job_id)

        # Persistent HA notification
        self._notify(title="AI Hub — Error", message=message)

        # Push to WebSocket clients
        if job_id:
            self._ws_broadcast(
                job_id=job_id,
                payload={
                    "type": "error",
                    "job_id": job_id,
                    "status": "error",
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        self.log(f"Error reported: {message}", level="ERROR")

    # ------------------------------------------------------------------
    # HA Entity Helpers
    # ------------------------------------------------------------------

    def _set_status(self, status: str) -> None:
        """Update the ai_hub_status input_text entity."""
        self.set_state(self._status_entity, state=status)

    def _set_error(self, message: str) -> None:
        """Update the ai_hub_error input_text entity."""
        self.set_state(self._error_entity, state=message[:255])

    def _notify(self, title: str, message: str) -> None:
        """Send a persistent HA notification."""
        try:
            self.call_service(
                "persistent_notification/create",
                title=title,
                message=message,
                notification_id="ai_hub_notification",
            )
        except Exception as exc:  # noqa: BLE001
            self.log(f"Failed to send HA notification: {exc}", level="WARNING")

    # ------------------------------------------------------------------
    # WebSocket Broadcast
    # ------------------------------------------------------------------

    def _ws_broadcast(self, job_id: str, payload: dict[str, Any]) -> None:
        """
        Push a JSON payload to all WebSocket clients subscribed to job_id.
        Called from a worker thread — uses asyncio.run_coroutine_threadsafe
        to safely schedule the coroutine on the AppDaemon event loop.
        """
        clients = self._ws_clients.get(job_id, set()).copy()
        # Also broadcast to the global channel (job_id="*")
        clients |= self._ws_clients.get("*", set()).copy()

        if not clients:
            return

        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(
            self._ws_send_all(clients, payload),
            loop,
        )

    async def _ws_send_all(
        self,
        clients: set,
        payload: dict[str, Any],
    ) -> None:
        """Async coroutine: send JSON to all WebSocket clients."""
        message = json.dumps(payload)
        dead: set = set()
        for ws in clients:
            try:
                await ws.send_str(message)
            except Exception:  # noqa: BLE001
                dead.add(ws)
        # Clean up closed connections
        for job_clients in self._ws_clients.values():
            job_clients -= dead

    # ------------------------------------------------------------------
    # aiohttp HTTP / WebSocket Endpoints
    # ------------------------------------------------------------------

    def _register_http_endpoints(self) -> None:
        """
        Register REST and WebSocket routes on AppDaemon's built-in
        aiohttp server.  AppDaemon exposes self.register_endpoint() for
        this purpose.
        """
        self.register_endpoint(self._http_trigger, "ai_hub/trigger")
        self.register_endpoint(self._http_status, "ai_hub/status")
        self.register_endpoint(self._http_result, "ai_hub/result")
        self.register_endpoint(self._http_ws, "ai_hub/ws")
        self.register_endpoint(self._http_settings_get, "ai_hub/settings")
        self.register_endpoint(self._http_settings_post, "ai_hub/settings/save")
        self.register_endpoint(self._http_settings_metadata, "ai_hub/settings/metadata")
        self.log("HTTP endpoints registered at /api/appdaemon/ai_hub/", level="INFO")

    async def _http_trigger(self, request: web.Request) -> web.Response:
        """
        POST /api/appdaemon/ai_hub/trigger
        Body: { "crew": "code_review", "prompt": "...", "options": {} }
        Returns: 202 Accepted { "job_id": "abc12345" }
        """
        try:
            body = await request.json()
        except Exception:
            return web.Response(
                status=400,
                text=json.dumps({"error": "Invalid JSON body"}),
                content_type="application/json",
            )

        crew_name = body.get("crew")
        prompt = body.get("prompt", "").strip()

        if not crew_name or not prompt:
            return web.Response(
                status=422,
                text=json.dumps({"error": "'crew' and 'prompt' are required"}),
                content_type="application/json",
            )

        job_id = str(uuid.uuid4())[:8]

        # Fire the HA event — the existing _on_trigger handler picks it up
        self.fire_event(
            self._trigger_event,
            crew=crew_name,
            prompt=prompt,
            options=body.get("options", {}),
            job_id=job_id,
        )

        return web.Response(
            status=202,
            text=json.dumps({"job_id": job_id, "status": "accepted"}),
            content_type="application/json",
        )

    async def _http_status(self, request: web.Request) -> web.Response:
        """
        GET /api/appdaemon/ai_hub/status
        Returns: { "status": "idle|running|done|error", "active_crew": "..." }
        """
        status = self.get_state(self._status_entity) or "idle"
        active_crew = self.get_state(self._active_crew_entity) or ""
        return web.Response(
            text=json.dumps({"status": status, "active_crew": active_crew}),
            content_type="application/json",
        )

    async def _http_result(self, request: web.Request) -> web.Response:
        """
        GET /api/appdaemon/ai_hub/result
        Returns: { "result": "...", "error": "..." }
        """
        result = self.get_state(self._result_entity) or ""
        error = self.get_state(self._error_entity) or ""
        return web.Response(
            text=json.dumps({"result": result, "error": error}),
            content_type="application/json",
        )

    async def _http_ws(self, request: web.Request) -> web.WebSocketResponse:
        """
        WebSocket /api/appdaemon/ai_hub/ws
        Query param: ?job_id=<id>  (use '*' to subscribe to all jobs)

        The server pushes JSON messages:
          { "type": "status", "status": "running", ... }
          { "type": "result", "result": "...", ... }
          { "type": "error",  "message": "...", ... }
        """
        job_id = request.rel_url.query.get("job_id", "*")

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Register this client
        self._ws_clients.setdefault(job_id, set()).add(ws)
        self.log(f"WebSocket client connected (job_id={job_id})", level="DEBUG")

        # Send current status immediately on connect
        await ws.send_str(
            json.dumps({
                "type": "status",
                "status": self.get_state(self._status_entity) or "idle",
                "active_crew": self.get_state(self._active_crew_entity) or "",
            })
        )

        try:
            async for msg in ws:
                # We don't expect messages from the client, but handle pings
                if msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            self._ws_clients.get(job_id, set()).discard(ws)
            self.log(f"WebSocket client disconnected (job_id={job_id})", level="DEBUG")

        return ws

    async def _http_settings_get(self, request: web.Request) -> web.Response:
        """
        GET /api/appdaemon/ai_hub/settings
        Returns current settings (API keys replaced with boolean flags).
        """
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

    async def _http_settings_post(self, request: web.Request) -> web.Response:
        """
        POST /api/appdaemon/ai_hub/settings/save
        Body: settings payload (see settings_manager.save_settings for schema).
        Writes to apps.yaml and secrets.yaml on the HA device.
        Returns: { "status": "ok", "message": "..." }
        """
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

    async def _http_settings_metadata(self, request: web.Request) -> web.Response:
        """
        GET /api/appdaemon/ai_hub/settings/metadata
        Returns static metadata: agent roles, provider→model lists.
        Used by the frontend to populate dropdowns without hardcoding.
        """
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
