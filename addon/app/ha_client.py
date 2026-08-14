"""
ha_client.py — Home Assistant Supervisor API Client
=====================================================
Replaces the hass.Hass AppDaemon base class.

In a custom HA add-on, the Supervisor injects SUPERVISOR_TOKEN into the
container environment. This token authenticates calls to:
  - http://supervisor/core/api/  — HA REST API (states, services, events)
  - ws://supervisor/core/websocket — HA WebSocket API (event subscriptions)

This module provides an async client that wraps both interfaces.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Callable

import aiohttp

logger = logging.getLogger("ai_hub.ha_client")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPERVISOR_URL = "http://supervisor/core/api"
SUPERVISOR_WS  = "ws://supervisor/core/websocket"


class HAClient:
    """
    Async client for the Home Assistant REST and WebSocket APIs.

    Usage:
        client = HAClient()
        await client.connect()
        state = await client.get_state("sensor.temperature")
        await client.set_state("input_text.ai_hub_status", "running")
        await client.call_service("notify", "notify", message="Done!")
        await client.close()
    """

    def __init__(self) -> None:
        self._token: str = os.environ.get("AI_HUB_SUPERVISOR_TOKEN", "")
        if not self._token:
            raise RuntimeError(
                "AI_HUB_SUPERVISOR_TOKEN is not set. "
                "Ensure hassio_api: true is set in config.yaml."
            )
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task | None = None
        self._ws_id: int = 1
        self._event_listeners: dict[str, list[Callable]] = {}
        self._ws_pending: dict[int, asyncio.Future] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Create the aiohttp session and connect the WebSocket."""
        self._session = aiohttp.ClientSession(headers=self._headers)
        await self._ws_connect()
        logger.info("HAClient connected to Supervisor API")

    async def close(self) -> None:
        """Close the WebSocket and HTTP session."""
        if self._ws_task:
            self._ws_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("HAClient disconnected")

    # ------------------------------------------------------------------
    # REST API — States
    # ------------------------------------------------------------------

    async def get_state(self, entity_id: str) -> str | None:
        """
        Return the state string of an HA entity, or None if not found.
        """
        url = f"{SUPERVISOR_URL}/states/{entity_id}"
        async with self._session.get(url) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            data = await resp.json()
            return data.get("state")

    async def get_state_full(self, entity_id: str) -> dict[str, Any] | None:
        """
        Return the full state object (state + attributes + last_changed).
        """
        url = f"{SUPERVISOR_URL}/states/{entity_id}"
        async with self._session.get(url) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            return await resp.json()

    async def set_state(
        self,
        entity_id: str,
        state: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """
        Write a state to an HA entity via the REST API.
        Creates the entity if it doesn't exist (virtual entities only).
        """
        url = f"{SUPERVISOR_URL}/states/{entity_id}"
        payload: dict[str, Any] = {"state": state}
        if attributes:
            payload["attributes"] = attributes
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # REST API — Services
    # ------------------------------------------------------------------

    async def call_service(
        self,
        domain: str,
        service: str,
        **data: Any,
    ) -> None:
        """
        Call a Home Assistant service.
        Example: await client.call_service("notify", "notify", message="Hello")
        """
        url = f"{SUPERVISOR_URL}/services/{domain}/{service}"
        async with self._session.post(url, json=data) as resp:
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # REST API — Events
    # ------------------------------------------------------------------

    async def fire_event(self, event_type: str, **event_data: Any) -> None:
        """Fire a custom HA event."""
        url = f"{SUPERVISOR_URL}/events/{event_type}"
        async with self._session.post(url, json=event_data) as resp:
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # WebSocket API — Event subscriptions
    # ------------------------------------------------------------------

    async def _ws_connect(self) -> None:
        """Connect to the HA WebSocket API and authenticate."""
        ws_headers = {"Authorization": f"Bearer {self._token}"}
        self._ws = await self._session.ws_connect(
            SUPERVISOR_WS,
            headers=ws_headers,
            heartbeat=30,
        )
        # HA WS protocol: first message is auth_required, then we send auth
        msg = await self._ws.receive_json()
        if msg.get("type") == "auth_required":
            await self._ws.send_json({"type": "auth", "access_token": self._token})
            auth_result = await self._ws.receive_json()
            if auth_result.get("type") != "auth_ok":
                raise RuntimeError(f"HA WebSocket auth failed: {auth_result}")

        # Start background listener task
        self._ws_task = asyncio.create_task(self._ws_listener())
        logger.debug("HA WebSocket connected and authenticated")

    async def _ws_listener(self) -> None:
        """Background task: receive WebSocket messages and dispatch to listeners."""
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._dispatch_ws_message(data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning("HA WebSocket closed/error: %s", msg)
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.error("HA WebSocket listener error: %s", exc)

    async def _dispatch_ws_message(self, data: dict[str, Any]) -> None:
        """Route incoming WebSocket messages to registered listeners."""
        msg_type = data.get("type")

        # Response to a command we sent
        if msg_type == "result":
            msg_id = data.get("id")
            if msg_id in self._ws_pending:
                future = self._ws_pending.pop(msg_id)
                if not future.done():
                    future.set_result(data)
            return

        # Event fired by HA
        if msg_type == "event":
            event = data.get("event", {})
            event_type = event.get("event_type", "")
            callbacks = self._event_listeners.get(event_type, [])
            for cb in callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(event_type, event.get("data", {}))
                    else:
                        cb(event_type, event.get("data", {}))
                except Exception as exc:  # noqa: BLE001
                    logger.error("Event listener error for '%s': %s", event_type, exc)

    async def _ws_send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a WebSocket command and wait for its result."""
        msg_id = self._ws_id
        self._ws_id += 1
        payload["id"] = msg_id

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._ws_pending[msg_id] = future

        await self._ws.send_json(payload)
        return await asyncio.wait_for(future, timeout=10.0)

    async def subscribe_events(
        self,
        event_type: str,
        callback: Callable,
    ) -> None:
        """
        Subscribe to a HA event type via WebSocket.
        The callback receives (event_type: str, data: dict).
        """
        self._event_listeners.setdefault(event_type, []).append(callback)
        await self._ws_send({
            "type": "subscribe_events",
            "event_type": event_type,
        })
        logger.info("Subscribed to HA event: '%s'", event_type)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    async def persistent_notification(self, title: str, message: str, notification_id: str = "ai_hub") -> None:
        """Create a persistent HA notification."""
        try:
            await self.call_service(
                "persistent_notification",
                "create",
                title=title,
                message=message,
                notification_id=notification_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to create HA notification: %s", exc)
