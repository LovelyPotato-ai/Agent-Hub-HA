"""
tools.py — Custom CrewAI Tools
================================
Provides two custom tools that CrewAI agents can invoke:

  GitHubCommitTool   — Commit a file to a GitHub repository via the GitHub API.
  HASensorReaderTool — Read the current state of a Home Assistant entity via
                       the AppDaemon API.

Both tools inherit from crewai.tools.BaseTool and define a Pydantic input
schema so CrewAI can validate arguments before calling _run().

Error handling:
  - GitHub rate limits, auth failures, and network errors are caught and
    returned as descriptive error strings (not raised) so the agent can
    decide how to proceed.
  - HA entity read errors are similarly returned as strings.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import TYPE_CHECKING, Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    # Avoid circular import — hass.Hass is only used for type hints
    import appdaemon.plugins.hass.hassapi as hass

logger = logging.getLogger("ai_hub")


# ===========================================================================
# GitHubCommitTool
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
        description=(
            "Branch to commit to. Defaults to the branch configured in "
            "apps.yaml (usually 'main')."
        ),
    )


class GitHubCommitTool(BaseTool):
    """
    Commit a file to a GitHub repository.

    The tool authenticates with a Personal Access Token (PAT) and uses the
    GitHub Contents API to create or update a file in the target repository.

    Retry behaviour:
      - On RateLimitExceeded: waits until the reset time (max 60 s) then retries once.
      - On transient network errors: retries up to 3 times with exponential backoff.
    """

    name: str = "github_commit"
    description: str = (
        "Commit a file to the configured GitHub repository. "
        "Provide the filename (repo-relative path), the full file content, "
        "and a descriptive commit message."
    )
    args_schema: type[BaseModel] = GitHubCommitInput

    # These are set at construction time and excluded from Pydantic serialisation
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
        # Store as private attributes (not Pydantic fields)
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
        """
        Execute the GitHub commit.

        Returns a success message string or an error description string.
        Never raises — errors are returned as strings so the agent can handle them.
        """
        target_branch = branch or self._default_branch

        try:
            import github3
        except ImportError:
            return (
                "ERROR: github3.py is not installed. "
                "Add 'github3.py' to python_packages in appdaemon.yaml."
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
                    "GitHub rate limit hit. Waiting %ds before retry (attempt %d/3).",
                    wait,
                    attempt,
                )
                time.sleep(wait)
            except github3.exceptions.AuthenticationFailed:
                return (
                    "ERROR: GitHub authentication failed. "
                    "Check that github_pat in secrets.yaml is valid and has "
                    "'Contents: read & write' permission."
                )
            except github3.exceptions.NotFoundError:
                return (
                    f"ERROR: Repository '{self._owner}/{self._repo}' or branch "
                    f"'{target_branch}' not found. "
                    "Check github_repo_owner, github_repo_name, and github_branch "
                    "in secrets.yaml."
                )
            except Exception as exc:  # noqa: BLE001
                wait = 2 ** attempt
                logger.warning(
                    "GitHub API error (attempt %d/3): %s. Retrying in %ds.",
                    attempt,
                    exc,
                    wait,
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
        """Perform the actual GitHub API call."""
        gh = github3.login(token=self._pat)
        repo = gh.repository(self._owner, self._repo)

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        # Check if the file already exists (needed for the SHA to update it)
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
            # File does not exist yet — create it
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
# HASensorReaderTool
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

    Uses the AppDaemon API (self.get_state) to fetch the entity's state
    and attributes directly from the HA state machine — no HTTP call needed.

    Returns a JSON-like string with state, attributes, and last_changed.
    """

    name: str = "ha_sensor_reader"
    description: str = (
        "Read the current state and attributes of any Home Assistant entity. "
        "Provide the entity_id (e.g. 'sensor.living_room_temperature'). "
        "Returns the state value, all attributes, and when it last changed."
    )
    args_schema: type[BaseModel] = HASensorReaderInput

    # AppDaemon hass.Hass instance — set at construction time
    _hass_app: Any

    def __init__(self, hass_app: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_hass_app", hass_app)

    def _run(self, entity_id: str) -> str:
        """
        Fetch entity state from HA via AppDaemon.

        Returns a descriptive string the agent can parse.
        Never raises — errors are returned as strings.
        """
        entity_id = entity_id.strip()

        try:
            state = self._hass_app.get_state(entity_id)
            if state is None:
                return (
                    f"ERROR: Entity '{entity_id}' not found in Home Assistant. "
                    "Check the entity_id spelling and ensure the entity exists."
                )

            attributes = self._hass_app.get_state(entity_id, attribute="all") or {}
            last_changed = attributes.get("last_changed", "unknown")
            attrs = attributes.get("attributes", {})

            # Build a readable summary
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

        except Exception as exc:  # noqa: BLE001
            logger.error("HASensorReaderTool error for '%s': %s", entity_id, exc)
            return f"ERROR: Failed to read entity '{entity_id}': {exc}"
