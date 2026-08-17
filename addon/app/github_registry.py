"""
github_registry.py — Named GitHub Connection Registry
======================================================
Manages user-defined GitHub connections stored in /data/github_repos.json.

Each connection contains:
  - id:          UUID (auto-generated)
  - name:        Human-readable display name
  - owner:       GitHub username or organisation
  - repo:        Repository name
  - branch:      Branch to commit to (default "main")
  - created_at:  ISO8601 timestamp
  - updated_at:  ISO8601 timestamp

One global PAT (stored in /data/options.json as github_pat) authenticates
all connections. Workflow tasks select a connection via github_repo_id.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_hub.github_registry")

DATA_DIR = Path(os.environ.get("AI_HUB_DATA_DIR", "/data"))
REPOS_FILE = DATA_DIR / "github_repos.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> list[dict[str, Any]]:
    if not REPOS_FILE.exists():
        return []
    try:
        with REPOS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to read github_repos.json: %s", exc)
        return []


def _write(repos: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REPOS_FILE.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(repos, f, indent=2)
        tmp.replace(REPOS_FILE)
    except Exception as exc:
        logger.error("Failed to write github_repos.json: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_repos() -> list[dict[str, Any]]:
    """Return all GitHub connections."""
    return _read()


def get_repo(repo_id: str) -> dict[str, Any] | None:
    """Return a single connection by ID, or None if not found."""
    for repo in _read():
        if repo["id"] == repo_id:
            return repo
    return None


def create_repo(data: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new GitHub connection.

    Required fields: name, owner, repo
    Optional fields: branch (defaults to "main")
    """
    name = str(data.get("name", "")).strip()
    owner = str(data.get("owner", "")).strip()
    repo = str(data.get("repo", "")).strip()
    if not name:
        raise ValueError("Connection name is required")
    if not owner:
        raise ValueError("Repository owner is required")
    if not repo:
        raise ValueError("Repository name is required")

    now = _now()
    connection: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "name": name,
        "owner": owner,
        "repo": repo,
        "branch": str(data.get("branch", "main") or "main"),
        "created_at": now,
        "updated_at": now,
    }
    repos = _read()
    repos.append(connection)
    _write(repos)
    logger.info("Created GitHub connection: %s (%s)", connection["name"], connection["id"])
    return connection


def update_repo(repo_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing connection. Returns updated connection or None if not found."""
    repos = _read()
    for i, connection in enumerate(repos):
        if connection["id"] == repo_id:
            updatable = {"name", "owner", "repo", "branch"}
            for key in updatable:
                if key in data:
                    connection[key] = str(data[key]).strip()
            if not connection.get("branch"):
                connection["branch"] = "main"
            connection["updated_at"] = _now()
            repos[i] = connection
            _write(repos)
            logger.info("Updated GitHub connection: %s (%s)", connection["name"], repo_id)
            return connection
    return None


def delete_repo(repo_id: str) -> bool:
    """Delete a connection by ID. Returns True if deleted, False if not found."""
    repos = _read()
    new_repos = [r for r in repos if r["id"] != repo_id]
    if len(new_repos) == len(repos):
        return False
    _write(new_repos)
    logger.info("Deleted GitHub connection: %s", repo_id)
    return True
