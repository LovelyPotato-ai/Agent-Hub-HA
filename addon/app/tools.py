"""
tools.py — Custom CrewAI Tools (Add-on version)
=================================================
Adapted from the AppDaemon version.

Changes vs AppDaemon version:
  - HASensorReaderTool accepts an HAClient instance instead of hass.Hass
  - HASensorReaderTool uses async HAClient.get_state_full() via asyncio.run()
    (CrewAI tools are called synchronously from worker threads)
  - GitHubCommitTool is unchanged

Both tools inherit from crewai.tools.BaseTool and define Pydantic input
schemas so CrewAI can validate arguments before calling _run().
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import TYPE_CHECKING, Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ha_client import HAClient

logger = logging.getLogger("ai_hub.tools")


# ===========================================================================
# GitHubCommitTool — unchanged from AppDaemon version
# ===========================================================================

class GitHubCommitInput(BaseModel):
    """Input schema for GitHubCommitTool."""

    filename: str = Field(
        ...,
        description=(
            "Path of the file to create or update in the repository, "
            "relative to the repo root. Example: 'automations/lights.yaml'"
        ),
    )
    content: str = Field(
        ...,
        description="Full text content to write to the file.",
    )
    commit_message: str = Field(
        ...,
        description="Git commit message describing the change.",
    )
    branch: Optional[str] = Field(
        default=None,
        description="Branch to commit to. Defaults to the configured branch.",
    )


class GitHubCommitTool(BaseTool):
    """
    Commit a file to a GitHub repository.

    Authenticates with a Personal Access Token (PAT) and uses the
    GitHub Contents API to create or update a file.

    Retry behaviour:
      - On RateLimitExceeded: waits until reset time (max 60s) then retries once.
      - On transient network errors: retries up to 3 times with exponential backoff.
    """

    name: str = "github_commit"
    description: str = (
        "Commit a file to the configured GitHub repository. "
        "Provide the filename (repo-relative path), the full file content, "
        "and a descriptive commit message."
    )
    args_schema: type[BaseModel] = GitHubCommitInput

    _pat: str
    _owner: str
    _repo: str
    _default_branch: str

    def __init__(
        self,
        pat: str,
        owner: str,
        repo: str,
        branch: str = "main",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_pat", pat)
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_repo", repo)
        object.__setattr__(self, "_default_branch", branch)

    def _run(
        self,
        filename: str,
        content: str,
        commit_message: str,
        branch: Optional[str] = None,
    ) -> str:
        target_branch = branch or self._default_branch

        try:
            import github3
        except ImportError:
            return (
                "ERROR: github3.py is not installed. "
                "Check requirements.txt in the add-on."
            )

        for attempt in range(1, 4):
            try:
                return self._do_commit(
                    github3=github3,
                    filename=filename,
                    content=content,
                    commit_message=commit_message,
                    branch=target_branch,
                )
            except github3.exceptions.RateLimitExceeded as exc:
                reset_in = max(0, int(exc.reset_at.timestamp() - time.time()))
                wait = min(reset_in + 1, 60)
                logger.warning(
                    "GitHub rate limit hit. Waiting %ds (attempt %d/3).", wait, attempt
                )
                time.sleep(wait)
            except github3.exceptions.AuthenticationFailed:
                return (
                    "ERROR: GitHub authentication failed. "
                    "Check that github_pat in the add-on configuration is valid "
                    "and has 'Contents: read & write' permission."
                )
            except github3.exceptions.NotFoundError:
                return (
                    f"ERROR: Repository '{self._owner}/{self._repo}' or branch "
                    f"'{target_branch}' not found. "
                    "Check github_repo_owner, github_repo_name, and github_branch "
                    "in the add-on configuration."
                )
            except Exception as exc:  # noqa: BLE001
                wait = 2 ** attempt
                logger.warning(
                    "GitHub API error (attempt %d/3): %s. Retrying in %ds.",
                    attempt, exc, wait,
                )
                if attempt == 3:
                    return f"ERROR: GitHub commit failed after 3 attempts: {exc}"
                time.sleep(wait)

        return "ERROR: GitHub commit failed after exhausting all retries."

    def _do_commit(
        self,
        github3: Any,
        filename: str,
        content: str,
        commit_message: str,
        branch: str,
    ) -> str:
        gh = github3.login(token=self._pat)
        repo = gh.repository(self._owner, self._repo)
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        try:
            existing = repo.file_contents(filename, ref=branch)
            sha = existing.sha
            result = repo.update_file(
                path=filename,
                message=commit_message,
                content=encoded_content,
                sha=sha,
                branch=branch,
            )
            action = "updated"
        except github3.exceptions.NotFoundError:
            result = repo.create_file(
                path=filename,
                message=commit_message,
                content=encoded_content,
                branch=branch,
            )
            action = "created"

        commit_sha = result["commit"].sha[:7]
        url = f"https://github.com/{self._owner}/{self._repo}/blob/{branch}/{filename}"
        logger.info("GitHub commit %s: %s (%s)", action, filename, commit_sha)
        return (
            f"SUCCESS: File '{filename}' {action} in "
            f"{self._owner}/{self._repo}@{branch}. "
            f"Commit: {commit_sha}. URL: {url}"
        )


# ===========================================================================
# HASensorReaderTool — adapted to use HAClient instead of hass.Hass
# ===========================================================================

class HASensorReaderInput(BaseModel):
    """Input schema for HASensorReaderTool."""

    entity_id: str = Field(
        ...,
        description=(
            "The Home Assistant entity ID to read. "
            "Examples: 'sensor.living_room_temperature', "
            "'binary_sensor.motion_hallway', 'switch.kitchen_light'."
        ),
    )


class HASensorReaderTool(BaseTool):
    """
    Read the current state of a Home Assistant entity.

    Uses the HAClient to call the HA Supervisor REST API.
    Since CrewAI tools are called synchronously from worker threads,
    we use asyncio.run_coroutine_threadsafe to call the async HAClient.
    """

    name: str = "ha_sensor_reader"
    description: str = (
        "Read the current state and attributes of any Home Assistant entity. "
        "Provide the entity_id (e.g. 'sensor.living_room_temperature'). "
        "Returns the state value, all attributes, and when it last changed."
    )
    args_schema: type[BaseModel] = HASensorReaderInput

    _ha_client: Any  # HAClient | None

    def __init__(self, ha_client: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_ha_client", ha_client)

    def _run(self, entity_id: str) -> str:
        entity_id = entity_id.strip()

        if self._ha_client is None:
            return (
                f"ERROR: HA client is not connected. "
                f"Cannot read entity '{entity_id}'."
            )

        try:
            # We're in a worker thread — use run_coroutine_threadsafe to call
            # the async HAClient from a synchronous context.
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(
                self._ha_client.get_state_full(entity_id),
                loop,
            )
            state_data = future.result(timeout=10.0)

            if state_data is None:
                return (
                    f"ERROR: Entity '{entity_id}' not found in Home Assistant. "
                    "Check the entity_id spelling and ensure the entity exists."
                )

            state = state_data.get("state", "unknown")
            last_changed = state_data.get("last_changed", "unknown")
            attrs = state_data.get("attributes", {})

            attr_lines = "\n".join(
                f"  {k}: {v}" for k, v in attrs.items()
            ) or "  (no attributes)"

            result = (
                f"Entity: {entity_id}\n"
                f"State: {state}\n"
                f"Last changed: {last_changed}\n"
                f"Attributes:\n{attr_lines}"
            )
            logger.debug("HASensorReaderTool: %s = %s", entity_id, state)
            return result

        except TimeoutError:
            return f"ERROR: Timeout reading entity '{entity_id}' from HA."
        except Exception as exc:  # noqa: BLE001
            logger.error("HASensorReaderTool error for '%s': %s", entity_id, exc)
            return f"ERROR: Failed to read entity '{entity_id}': {exc}"
