"""
agent_registry.py — Dynamic Agent Registry
============================================
Manages user-defined agents stored in /data/agents.json.

Each agent definition contains:
  - id:               UUID (auto-generated)
  - name:             Human-readable display name
  - role:             CrewAI agent role (e.g. "Senior Developer")
  - goal:             What the agent is trying to achieve
  - backstory:        Personality / expertise context
  - tools:            List of tool IDs (see tool_factory.py)
  - llm_override:     Optional {"provider": "openai", "model": "gpt-4o"} — overrides global LLM
  - allow_delegation: Whether the agent can delegate to others
  - max_iter:         Max reasoning iterations (default 5)
  - created_at:       ISO8601 timestamp
  - updated_at:       ISO8601 timestamp
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_hub.agent_registry")

DATA_DIR = Path(os.environ.get("AI_HUB_DATA_DIR", "/data"))
AGENTS_FILE = DATA_DIR / "agents.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> list[dict[str, Any]]:
    if not AGENTS_FILE.exists():
        return []
    try:
        with AGENTS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to read agents.json: %s", exc)
        return []


def _write(agents: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = AGENTS_FILE.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(agents, f, indent=2)
        tmp.replace(AGENTS_FILE)
    except Exception as exc:
        logger.error("Failed to write agents.json: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_agents() -> list[dict[str, Any]]:
    """Return all agent definitions."""
    return _read()


def get_agent(agent_id: str) -> dict[str, Any] | None:
    """Return a single agent by ID, or None if not found."""
    for agent in _read():
        if agent["id"] == agent_id:
            return agent
    return None


def create_agent(data: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new agent definition.

    Required fields: name, role, goal, backstory
    Optional fields: tools, llm_override, allow_delegation, max_iter
    """
    now = _now()
    agent: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "name": str(data.get("name", "Unnamed Agent")),
        "role": str(data.get("role", "Agent")),
        "goal": str(data.get("goal", "")),
        "backstory": str(data.get("backstory", "")),
        "tools": list(data.get("tools", [])),
        "llm_override": data.get("llm_override"),  # None or {"provider": ..., "model": ...}
        "allow_delegation": bool(data.get("allow_delegation", False)),
        "max_iter": int(data.get("max_iter", 5)),
        "created_at": now,
        "updated_at": now,
    }
    agents = _read()
    agents.append(agent)
    _write(agents)
    logger.info("Created agent: %s (%s)", agent["name"], agent["id"])
    return agent


def update_agent(agent_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing agent. Returns updated agent or None if not found."""
    agents = _read()
    for i, agent in enumerate(agents):
        if agent["id"] == agent_id:
            updatable = {"name", "role", "goal", "backstory", "tools",
                         "llm_override", "allow_delegation", "max_iter"}
            for key in updatable:
                if key in data:
                    agent[key] = data[key]
            agent["updated_at"] = _now()
            agents[i] = agent
            _write(agents)
            logger.info("Updated agent: %s (%s)", agent["name"], agent_id)
            return agent
    return None


def delete_agent(agent_id: str) -> bool:
    """Delete an agent by ID. Returns True if deleted, False if not found."""
    agents = _read()
    new_agents = [a for a in agents if a["id"] != agent_id]
    if len(new_agents) == len(agents):
        return False
    _write(new_agents)
    logger.info("Deleted agent: %s", agent_id)
    return True


def upsert_agent(data: dict[str, Any]) -> dict[str, Any]:
    """
    Insert or update an agent by ID.
    Used by seed_defaults.py to create default agents without duplicating.
    """
    agent_id = data.get("id")
    if agent_id and get_agent(agent_id):
        return update_agent(agent_id, data) or data
    # Force the ID if provided
    agents = _read()
    now = _now()
    agent: dict[str, Any] = {
        "id": agent_id or str(uuid.uuid4()),
        "name": str(data.get("name", "Unnamed Agent")),
        "role": str(data.get("role", "Agent")),
        "goal": str(data.get("goal", "")),
        "backstory": str(data.get("backstory", "")),
        "tools": list(data.get("tools", [])),
        "llm_override": data.get("llm_override"),
        "allow_delegation": bool(data.get("allow_delegation", False)),
        "max_iter": int(data.get("max_iter", 5)),
        "created_at": data.get("created_at", now),
        "updated_at": now,
    }
    agents.append(agent)
    _write(agents)
    return agent
