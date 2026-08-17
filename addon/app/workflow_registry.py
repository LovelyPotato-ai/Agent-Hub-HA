"""
workflow_registry.py — Dynamic Workflow Registry
==================================================
Manages user-defined workflows stored in /data/workflows.json.

A workflow is a DAG of tasks. Each task:
  - Has an assigned agent
  - Has a list of task IDs it depends on (context sources)
  - Has a description (may include {prompt} placeholder)
  - Has an expected_output description

Execution modes:
  - "sequential": tasks run in dependency order, each gets previous output as context
  - "hierarchical": a manager LLM orchestrates agents and can delegate
  - "dag": topological sort with parallel execution of independent branches
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_hub.workflow_registry")

DATA_DIR = Path(os.environ.get("AI_HUB_DATA_DIR", "/data"))
WORKFLOWS_FILE = DATA_DIR / "workflows.json"

VALID_PROCESSES = {"sequential", "hierarchical", "dag"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> list[dict[str, Any]]:
    if not WORKFLOWS_FILE.exists():
        return []
    try:
        with WORKFLOWS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to read workflows.json: %s", exc)
        return []


def _write(workflows: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = WORKFLOWS_FILE.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(workflows, f, indent=2)
        tmp.replace(WORKFLOWS_FILE)
    except Exception as exc:
        logger.error("Failed to write workflows.json: %s", exc)
        raise


def _normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Ensure a task dict has all required fields with defaults."""
    return {
        "id": task.get("id") or str(uuid.uuid4()),
        "name": str(task.get("name", "Unnamed Task")),
        "description": str(task.get("description", "")),
        "agent_id": str(task.get("agent_id", "")),
        "github_repo_id": task.get("github_repo_id", ""),  # empty = use first/default connection
        "expected_output": str(task.get("expected_output", "Task output")),
        "depends_on": list(task.get("depends_on", [])),
        "allow_delegation": bool(task.get("allow_delegation", False)),
        # UI layout hints (React Flow node position)
        "position": task.get("position", {"x": 0, "y": 0}),
    }


def _validate_dag(tasks: list[dict[str, Any]]) -> None:
    """Raise ValueError if the task graph has cycles."""
    task_ids = {t["id"] for t in tasks}
    # Check all depends_on references exist
    for task in tasks:
        for dep in task.get("depends_on", []):
            if dep not in task_ids:
                raise ValueError(
                    f"Task '{task['name']}' depends on unknown task ID '{dep}'"
                )
    # Cycle detection via DFS
    visited: set[str] = set()
    rec_stack: set[str] = set()
    adj: dict[str, list[str]] = {t["id"]: t.get("depends_on", []) for t in tasks}

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        for neighbour in adj.get(node, []):
            if neighbour not in visited:
                if dfs(neighbour):
                    return True
            elif neighbour in rec_stack:
                # Already visited AND still on the recursion stack → cycle
                return True
            # else: already fully processed (visited but not in rec_stack) → safe
        rec_stack.discard(node)
        return False

    for task_id in task_ids:
        if task_id not in visited:
            if dfs(task_id):
                raise ValueError("Workflow contains a cycle in task dependencies")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_workflows() -> list[dict[str, Any]]:
    """Return all workflow definitions."""
    return _read()


def get_workflow(workflow_id: str) -> dict[str, Any] | None:
    """Return a single workflow by ID, or None if not found."""
    for wf in _read():
        if wf["id"] == workflow_id:
            return wf
    return None


def create_workflow(data: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new workflow definition.

    Required fields: name
    Optional fields: description, process, manager_llm, tasks
    """
    process = data.get("process", "sequential")
    if process not in VALID_PROCESSES:
        raise ValueError(f"Invalid process '{process}'. Choose from: {VALID_PROCESSES}")

    tasks = [_normalize_task(t) for t in data.get("tasks", [])]
    _validate_dag(tasks)

    now = _now()
    workflow: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "name": str(data.get("name", "Unnamed Workflow")),
        "description": str(data.get("description", "")),
        "process": process,
        "manager_llm": data.get("manager_llm"),  # None or {"provider": ..., "model": ...}
        "tasks": tasks,
        "created_at": now,
        "updated_at": now,
    }
    workflows = _read()
    workflows.append(workflow)
    _write(workflows)
    logger.info("Created workflow: %s (%s)", workflow["name"], workflow["id"])
    return workflow


def update_workflow(workflow_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing workflow. Returns updated workflow or None if not found."""
    workflows = _read()
    for i, wf in enumerate(workflows):
        if wf["id"] == workflow_id:
            if "name" in data:
                wf["name"] = str(data["name"])
            if "description" in data:
                wf["description"] = str(data["description"])
            if "process" in data:
                process = data["process"]
                if process not in VALID_PROCESSES:
                    raise ValueError(f"Invalid process '{process}'")
                wf["process"] = process
            if "manager_llm" in data:
                wf["manager_llm"] = data["manager_llm"]
            if "tasks" in data:
                tasks = [_normalize_task(t) for t in data["tasks"]]
                _validate_dag(tasks)
                wf["tasks"] = tasks
            wf["updated_at"] = _now()
            workflows[i] = wf
            _write(workflows)
            logger.info("Updated workflow: %s (%s)", wf["name"], workflow_id)
            return wf
    return None


def delete_workflow(workflow_id: str) -> bool:
    """Delete a workflow by ID. Returns True if deleted, False if not found."""
    workflows = _read()
    new_workflows = [w for w in workflows if w["id"] != workflow_id]
    if len(new_workflows) == len(workflows):
        return False
    _write(new_workflows)
    logger.info("Deleted workflow: %s", workflow_id)
    return True


def upsert_workflow(data: dict[str, Any]) -> dict[str, Any]:
    """
    Insert or update a workflow by ID.
    Used by seed_defaults.py to create default workflows without duplicating.
    """
    workflow_id = data.get("id")
    if workflow_id and get_workflow(workflow_id):
        return get_workflow(workflow_id) or data  # Don't overwrite user edits

    process = data.get("process", "sequential")
    tasks = [_normalize_task(t) for t in data.get("tasks", [])]
    now = _now()
    workflow: dict[str, Any] = {
        "id": workflow_id or str(uuid.uuid4()),
        "name": str(data.get("name", "Unnamed Workflow")),
        "description": str(data.get("description", "")),
        "process": process,
        "manager_llm": data.get("manager_llm"),
        "tasks": tasks,
        "created_at": data.get("created_at", now),
        "updated_at": now,
    }
    workflows = _read()
    workflows.append(workflow)
    _write(workflows)
    return workflow
