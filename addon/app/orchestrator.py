"""
orchestrator.py — AI Hub Orchestrator
=======================================
Bridges the HA event bus (via HAClient) with the dynamic CrewAI system.

Exposes aiohttp request handlers registered by server.py.

HTTP API:
  GET  /api/agents              — list agents
  POST /api/agents              — create agent
  GET  /api/agents/{id}         — get agent
  PUT  /api/agents/{id}         — update agent
  DEL  /api/agents/{id}         — delete agent

  GET  /api/workflows           — list workflows
  POST /api/workflows           — create workflow
  GET  /api/workflows/{id}      — get workflow
  PUT  /api/workflows/{id}      — update workflow
  DEL  /api/workflows/{id}      — delete workflow

  GET  /api/tools               — list available tools

  POST /api/run/workflow/{id}   — run a workflow
  POST /api/run/agent/{id}      — run a single agent

  POST /api/trigger             — legacy: trigger by workflow name (backward compat)
  GET  /api/status              — current hub status
  GET  /api/result              — last result
  GET  /api/ws                  — WebSocket for real-time updates
  GET  /api/settings            — load settings
  POST /api/settings/save       — save settings
  GET  /api/settings/metadata   — settings metadata
  GET  /api/health              — health check
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

import aiohttp
from aiohttp import web

from agent_registry import (
    create_agent, delete_agent, get_agent, list_agents, update_agent,
)
from crew_executor import CrewExecutor
from ha_client import HAClient
from llm_factory import get_llm
from seed_defaults import seed
from settings_manager import get_metadata, load_settings, save_settings
from tool_factory import ToolFactory
from workflow_registry import (
    create_workflow, delete_workflow, get_workflow, list_workflows, update_workflow,
)

logger = logging.getLogger("ai_hub.orchestrator")

# ---------------------------------------------------------------------------
# HA entity IDs (virtual entities written via REST API)
# ---------------------------------------------------------------------------
ENTITY_STATUS      = "input_text.ai_hub_status"
ENTITY_RESULT      = "input_text.ai_hub_result"
ENTITY_ACTIVE_CREW = "input_text.ai_hub_active_crew"
ENTITY_ERROR       = "input_text.ai_hub_error"
TRIGGER_EVENT      = "ai_hub_trigger"


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_ok(data: Any, status: int = 200) -> web.Response:
    return web.Response(
        status=status,
        text=json.dumps(data),
        content_type="application/json",
    )


def _json_err(message: str, status: int = 400) -> web.Response:
    return web.Response(
        status=status,
        text=json.dumps({"error": message}),
        content_type="application/json",
    )


class AIHubOrchestrator:
    """
    Dynamic AI Hub orchestrator.

    Lifecycle:
      await orchestrator.start()   — seed defaults, init LLM + tools, subscribe to HA events
      await orchestrator.stop()    — clean up thread pool
    """

    def __init__(self, ha_client: HAClient | None) -> None:
        self._ha = ha_client
        self._ws_clients: dict[str, set] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=3,
            thread_name_prefix="ai_hub_crew",
        )
        # Separate executor for crew.kickoff() calls so they never share the
        # thread pool with _run_workflow_sync/_run_agent_sync (deadlock prevention).
        self._crew_kickoff_executor = ThreadPoolExecutor(
            max_workers=3,
            thread_name_prefix="ai_hub_kickoff",
        )
        self._llm: Any = None
        self._tool_factory: ToolFactory | None = None
        self._crew_executor: CrewExecutor | None = None
        # The running event loop — stored at start() time so sync threads can
        # schedule coroutines back onto it without calling get_event_loop().
        self._loop: asyncio.AbstractEventLoop | None = None
        # Track current job
        self._current_status = "idle"
        self._current_crew = ""
        self._last_result = ""
        self._last_error = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Seed defaults, initialise LLM + tools, subscribe to HA events."""
        self._loop = asyncio.get_running_loop()
        logger.info("AI Hub Orchestrator starting…")

        # ── Seed default agents and workflows ──────────────────────────
        try:
            seed()
        except Exception as exc:
            logger.error("Failed to seed defaults: %s", exc)

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
            self._last_error = str(exc)
            self._current_status = "error"

        # ── Tool factory ───────────────────────────────────────────────
        self._tool_factory = ToolFactory(ha_client=self._ha)

        # ── Crew executor ──────────────────────────────────────────────
        self._crew_executor = CrewExecutor(
            tool_factory=self._tool_factory,
            default_llm=self._llm,
            kickoff_executor=self._crew_kickoff_executor,
        )

        # ── Subscribe to HA trigger event ──────────────────────────────
        if self._ha:
            await self._ha.subscribe_events(TRIGGER_EVENT, self._on_trigger)
            logger.info("Subscribed to HA event: '%s'", TRIGGER_EVENT)

        if self._current_status != "error":
            self._current_status = "idle"
        await self._set_status(self._current_status)
        logger.info("AI Hub Orchestrator ready.")

    async def stop(self) -> None:
        """Shut down the thread pools."""
        self._executor.shutdown(wait=False)
        self._crew_kickoff_executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # HA Event Handler
    # ------------------------------------------------------------------

    async def _on_trigger(self, event_type: str, data: dict[str, Any]) -> None:
        """Called when the 'ai_hub_trigger' HA event fires."""
        logger.info("Received trigger event: %s", data)

        workflow_id = data.get("workflow_id", "").strip()
        agent_id    = data.get("agent_id", "").strip()
        prompt      = data.get("prompt", "").strip()

        if not prompt:
            await self._report_error("Trigger payload missing 'prompt' field.")
            return

        job_id = str(uuid.uuid4())[:8]
        loop = asyncio.get_running_loop()

        if workflow_id:
            await loop.run_in_executor(
                self._executor,
                self._run_workflow_sync,
                job_id, workflow_id, prompt,
            )
        elif agent_id:
            await loop.run_in_executor(
                self._executor,
                self._run_agent_sync,
                job_id, agent_id, prompt,
            )
        else:
            await self._report_error("Trigger payload must include 'workflow_id' or 'agent_id'.")

    # ------------------------------------------------------------------
    # Execution (sync wrappers for thread pool)
    # ------------------------------------------------------------------

    def _run_workflow_sync(self, job_id: str, workflow_id: str, prompt: str) -> None:
        # NOTE: This runs in a ThreadPoolExecutor thread.
        # self._loop is the main event loop captured at start() time.
        # We use run_coroutine_threadsafe to schedule async work back onto it.
        # crew_executor.run_workflow itself calls loop.run_in_executor — we pass
        # self._crew_kickoff_executor (a *separate* pool) to avoid deadlocking
        # the ai_hub_crew pool that is currently running this very function.
        loop = self._loop
        assert loop is not None, "Orchestrator not started"
        wf = get_workflow(workflow_id)
        name = wf["name"] if wf else workflow_id
        asyncio.run_coroutine_threadsafe(self._set_status("running"), loop).result(timeout=10)
        self._current_crew = name
        try:
            result = asyncio.run_coroutine_threadsafe(
                self._crew_executor.run_workflow(workflow_id, prompt), loop
            ).result(timeout=600)
            asyncio.run_coroutine_threadsafe(
                self._report_result(job_id, name, result), loop
            ).result(timeout=30)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("[%s] Workflow error:\n%s", job_id, tb)
            asyncio.run_coroutine_threadsafe(
                self._report_error(f"[{name}] {type(exc).__name__}: {exc}", job_id=job_id), loop
            ).result(timeout=10)

    def _run_agent_sync(self, job_id: str, agent_id: str, prompt: str) -> None:
        loop = self._loop
        assert loop is not None, "Orchestrator not started"
        ag = get_agent(agent_id)
        name = ag["name"] if ag else agent_id
        asyncio.run_coroutine_threadsafe(self._set_status("running"), loop).result(timeout=10)
        self._current_crew = name
        try:
            result = asyncio.run_coroutine_threadsafe(
                self._crew_executor.run_agent(agent_id, prompt), loop
            ).result(timeout=300)
            asyncio.run_coroutine_threadsafe(
                self._report_result(job_id, name, result), loop
            ).result(timeout=30)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("[%s] Agent error:\n%s", job_id, tb)
            asyncio.run_coroutine_threadsafe(
                self._report_error(f"[{name}] {type(exc).__name__}: {exc}", job_id=job_id), loop
            ).result(timeout=10)

    # ------------------------------------------------------------------
    # Result & Error Reporting
    # ------------------------------------------------------------------

    async def _report_result(self, job_id: str, name: str, result: str) -> None:
        truncated = result[:252] + "…" if len(result) > 255 else result
        self._current_status = "done"
        self._last_result = result
        self._last_error = ""
        if self._ha:
            await self._ha.set_state(ENTITY_RESULT, truncated)
            await self._ha.persistent_notification(
                title=f"AI Hub — {name} finished",
                message=truncated,
            )
        await self._set_status("done")
        self._ws_broadcast(job_id, {
            "type": "result",
            "job_id": job_id,
            "crew": name,
            "status": "done",
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info("[%s] Result reported.", job_id)

    async def _report_error(self, message: str, job_id: str = "") -> None:
        self._current_status = "error"
        self._last_error = message
        if self._ha:
            await self._ha.set_state(ENTITY_ERROR, message[:255])
            await self._ha.fire_event("ai_hub_error", message=message, job_id=job_id)
            await self._ha.persistent_notification(title="AI Hub — Error", message=message)
        await self._set_status("error")
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
        self._current_status = status
        if self._ha:
            try:
                await self._ha.set_state(ENTITY_STATUS, status)
            except Exception as exc:
                logger.warning("Failed to set HA status entity: %s", exc)

    # ------------------------------------------------------------------
    # WebSocket Broadcast
    # ------------------------------------------------------------------

    def _ws_broadcast(self, job_id: str, payload: dict[str, Any]) -> None:
        clients = self._ws_clients.get(job_id, set()).copy()
        clients |= self._ws_clients.get("*", set()).copy()
        if not clients:
            return
        loop = self._loop
        if loop is None:
            return
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
            except Exception:
                dead.add(ws)
        for job_clients in self._ws_clients.values():
            job_clients -= dead

    # ==================================================================
    # HTTP Handlers — Agents
    # ==================================================================

    async def http_agents_list(self, request: web.Request) -> web.Response:
        """GET /api/agents"""
        return _json_ok(list_agents())

    async def http_agents_create(self, request: web.Request) -> web.Response:
        """POST /api/agents"""
        try:
            body = await request.json()
        except Exception:
            return _json_err("Invalid JSON body")
        try:
            agent = create_agent(body)
            return _json_ok(agent, status=201)
        except ValueError as exc:
            return _json_err(str(exc))

    async def http_agents_get(self, request: web.Request) -> web.Response:
        """GET /api/agents/{id}"""
        agent_id = request.match_info["id"]
        agent = get_agent(agent_id)
        if not agent:
            return _json_err(f"Agent '{agent_id}' not found", status=404)
        return _json_ok(agent)

    async def http_agents_update(self, request: web.Request) -> web.Response:
        """PUT /api/agents/{id}"""
        agent_id = request.match_info["id"]
        try:
            body = await request.json()
        except Exception:
            return _json_err("Invalid JSON body")
        agent = update_agent(agent_id, body)
        if not agent:
            return _json_err(f"Agent '{agent_id}' not found", status=404)
        return _json_ok(agent)

    async def http_agents_delete(self, request: web.Request) -> web.Response:
        """DELETE /api/agents/{id}"""
        agent_id = request.match_info["id"]
        if not delete_agent(agent_id):
            return _json_err(f"Agent '{agent_id}' not found", status=404)
        return _json_ok({"status": "deleted"})

    # ==================================================================
    # HTTP Handlers — Workflows
    # ==================================================================

    async def http_workflows_list(self, request: web.Request) -> web.Response:
        """GET /api/workflows"""
        return _json_ok(list_workflows())

    async def http_workflows_create(self, request: web.Request) -> web.Response:
        """POST /api/workflows"""
        try:
            body = await request.json()
        except Exception:
            return _json_err("Invalid JSON body")
        try:
            workflow = create_workflow(body)
            return _json_ok(workflow, status=201)
        except ValueError as exc:
            return _json_err(str(exc))

    async def http_workflows_get(self, request: web.Request) -> web.Response:
        """GET /api/workflows/{id}"""
        workflow_id = request.match_info["id"]
        workflow = get_workflow(workflow_id)
        if not workflow:
            return _json_err(f"Workflow '{workflow_id}' not found", status=404)
        return _json_ok(workflow)

    async def http_workflows_update(self, request: web.Request) -> web.Response:
        """PUT /api/workflows/{id}"""
        workflow_id = request.match_info["id"]
        try:
            body = await request.json()
        except Exception:
            return _json_err("Invalid JSON body")
        try:
            workflow = update_workflow(workflow_id, body)
        except ValueError as exc:
            return _json_err(str(exc))
        if not workflow:
            return _json_err(f"Workflow '{workflow_id}' not found", status=404)
        return _json_ok(workflow)

    async def http_workflows_delete(self, request: web.Request) -> web.Response:
        """DELETE /api/workflows/{id}"""
        workflow_id = request.match_info["id"]
        if not delete_workflow(workflow_id):
            return _json_err(f"Workflow '{workflow_id}' not found", status=404)
        return _json_ok({"status": "deleted"})

    # ==================================================================
    # HTTP Handlers — Tools
    # ==================================================================

    async def http_tools_list(self, request: web.Request) -> web.Response:
        """GET /api/tools"""
        return _json_ok(ToolFactory.list_definitions())

    # ==================================================================
    # HTTP Handlers — Run
    # ==================================================================

    async def http_run_workflow(self, request: web.Request) -> web.Response:
        """POST /api/run/workflow/{id}"""
        workflow_id = request.match_info["id"]
        try:
            body = await request.json()
        except Exception:
            return _json_err("Invalid JSON body")

        prompt = body.get("prompt", "").strip()
        if not prompt:
            return _json_err("'prompt' is required")

        workflow = get_workflow(workflow_id)
        if not workflow:
            return _json_err(f"Workflow '{workflow_id}' not found", status=404)

        if not self._crew_executor:
            return _json_err("Orchestrator not ready", status=503)

        job_id = str(uuid.uuid4())[:8]
        await self._set_status("running")
        self._current_crew = workflow["name"]

        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            self._executor,
            self._run_workflow_sync,
            job_id, workflow_id, prompt,
        )

        return _json_ok({"job_id": job_id, "status": "accepted"}, status=202)

    async def http_run_agent(self, request: web.Request) -> web.Response:
        """POST /api/run/agent/{id}"""
        agent_id = request.match_info["id"]
        try:
            body = await request.json()
        except Exception:
            return _json_err("Invalid JSON body")

        prompt = body.get("prompt", "").strip()
        if not prompt:
            return _json_err("'prompt' is required")

        agent = get_agent(agent_id)
        if not agent:
            return _json_err(f"Agent '{agent_id}' not found", status=404)

        if not self._crew_executor:
            return _json_err("Orchestrator not ready", status=503)

        job_id = str(uuid.uuid4())[:8]
        await self._set_status("running")
        self._current_crew = agent["name"]

        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            self._executor,
            self._run_agent_sync,
            job_id, agent_id, prompt,
        )

        return _json_ok({"job_id": job_id, "status": "accepted"}, status=202)

    # ==================================================================
    # HTTP Handlers — Legacy / Status / WebSocket
    # ==================================================================

    async def http_trigger(self, request: web.Request) -> web.Response:
        """POST /api/trigger — legacy endpoint, routes to workflow by name or ID."""
        try:
            body = await request.json()
        except Exception:
            return _json_err("Invalid JSON body")

        prompt = body.get("prompt", "").strip()
        if not prompt:
            return _json_err("'prompt' is required")

        # Support legacy 'crew' field by mapping to workflow name
        crew_name = body.get("crew", "").strip()
        workflow_id = body.get("workflow_id", "").strip()
        agent_id = body.get("agent_id", "").strip()

        if not workflow_id and crew_name:
            # Find workflow by name (case-insensitive, normalise spaces→underscores)
            crew_name_norm = crew_name.lower().replace(" ", "_")
            for wf in list_workflows():
                if wf["name"].lower().replace(" ", "_") == crew_name_norm:
                    workflow_id = wf["id"]
                    break

        if not workflow_id and not agent_id:
            return _json_err("'workflow_id', 'agent_id', or 'crew' is required")

        if not self._crew_executor:
            return _json_err("Orchestrator not ready", status=503)

        job_id = str(uuid.uuid4())[:8]
        await self._set_status("running")

        loop = asyncio.get_running_loop()
        if workflow_id:
            wf = get_workflow(workflow_id)
            self._current_crew = wf["name"] if wf else workflow_id
            loop.run_in_executor(
                self._executor, self._run_workflow_sync, job_id, workflow_id, prompt
            )
        else:
            ag = get_agent(agent_id)
            self._current_crew = ag["name"] if ag else agent_id
            loop.run_in_executor(
                self._executor, self._run_agent_sync, job_id, agent_id, prompt
            )

        return _json_ok({"job_id": job_id, "status": "accepted"}, status=202)

    async def http_status(self, request: web.Request) -> web.Response:
        """GET /api/status"""
        status = self._current_status
        active_crew = self._current_crew
        if self._ha:
            status = await self._ha.get_state(ENTITY_STATUS) or status
            active_crew = await self._ha.get_state(ENTITY_ACTIVE_CREW) or active_crew
        return _json_ok({"status": status, "active_crew": active_crew})

    async def http_result(self, request: web.Request) -> web.Response:
        """GET /api/result"""
        result = self._last_result
        error  = self._last_error
        if self._ha:
            result = await self._ha.get_state(ENTITY_RESULT) or result
            error  = await self._ha.get_state(ENTITY_ERROR) or error
        return _json_ok({"result": result, "error": error})

    async def http_ws(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket /api/ws?job_id=<id>"""
        job_id = request.rel_url.query.get("job_id", "*")
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._ws_clients.setdefault(job_id, set()).add(ws)
        logger.debug("WebSocket client connected (job_id=%s)", job_id)

        # Send current status immediately
        await ws.send_str(json.dumps({
            "type": "status",
            "status": self._current_status,
            "active_crew": self._current_crew,
        }))

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.ERROR:
                    break
        finally:
            self._ws_clients.get(job_id, set()).discard(ws)
            logger.debug("WebSocket client disconnected (job_id=%s)", job_id)

        return ws

    async def http_settings_get(self, request: web.Request) -> web.Response:
        """GET /api/settings"""
        try:
            loop = asyncio.get_running_loop()
            settings = await loop.run_in_executor(None, load_settings)
            return _json_ok(settings)
        except Exception as exc:
            return _json_err(str(exc), status=500)

    async def http_settings_post(self, request: web.Request) -> web.Response:
        """POST /api/settings/save"""
        try:
            body = await request.json()
        except Exception:
            return _json_err("Invalid JSON body")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, save_settings, body)
        status_code = 200 if result.get("status") == "ok" else 500
        return web.Response(status=status_code, text=json.dumps(result), content_type="application/json")

    async def http_settings_metadata(self, request: web.Request) -> web.Response:
        """GET /api/settings/metadata"""
        try:
            loop = asyncio.get_running_loop()
            metadata = await loop.run_in_executor(None, get_metadata)
            return _json_ok(metadata)
        except Exception as exc:
            return _json_err(str(exc), status=500)
