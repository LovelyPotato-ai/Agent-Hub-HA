"""
tool_factory.py — Tool Registry and Factory
=============================================
Maps tool IDs (strings) to CrewAI tool instances.

Available tools:
  "ha_sensor_reader"  — Read HA entity states via Supervisor API
  "github_commit"     — Commit files to a GitHub repository

Tools are instantiated with the shared HAClient and config from environment
variables. The factory is called once at orchestrator startup and the tool
instances are reused across all crew executions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ha_client import HAClient

from tools import GitHubCommitTool, HASensorReaderTool

logger = logging.getLogger("ai_hub.tool_factory")

# ---------------------------------------------------------------------------
# Tool metadata (for the frontend /api/tools endpoint)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, str]] = [
    {
        "id": "ha_sensor_reader",
        "name": "HA Sensor Reader",
        "description": (
            "Reads the current state of one or more Home Assistant entities. "
            "Accepts a comma-separated list of entity IDs and returns their "
            "state, attributes, and last-changed timestamp."
        ),
    },
    {
        "id": "github_commit",
        "name": "GitHub Commit",
        "description": (
            "Creates or updates a file in a GitHub repository and commits it. "
            "Requires a GitHub Personal Access Token configured in Settings."
        ),
    },
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class ToolFactory:
    """
    Holds shared tool instances and resolves tool IDs to CrewAI tool objects.

    Usage:
        factory = ToolFactory(ha_client=ha_client)
        tools = factory.get_tools(["ha_sensor_reader", "github_commit"])
    """

    def __init__(self, ha_client: "HAClient | None") -> None:
        import os
        self._ha_sensor_tool = HASensorReaderTool(ha_client=ha_client)
        self._github_tool = GitHubCommitTool(
            pat=os.environ.get("AI_HUB_GITHUB_PAT", ""),
            owner=os.environ.get("AI_HUB_GITHUB_OWNER", ""),
            repo=os.environ.get("AI_HUB_GITHUB_REPO", ""),
            branch=os.environ.get("AI_HUB_GITHUB_BRANCH", "main"),
        )
        self._registry: dict[str, Any] = {
            "ha_sensor_reader": self._ha_sensor_tool,
            "github_commit": self._github_tool,
        }

    def get_tools(self, tool_ids: list[str]) -> list[Any]:
        """
        Resolve a list of tool IDs to CrewAI tool instances.
        Unknown IDs are logged and skipped.
        """
        result = []
        for tool_id in tool_ids:
            tool = self._registry.get(tool_id)
            if tool is None:
                logger.warning("Unknown tool ID '%s' — skipping", tool_id)
            else:
                result.append(tool)
        return result

    def get_github_tool(self) -> GitHubCommitTool:
        return self._github_tool

    def get_ha_sensor_tool(self) -> HASensorReaderTool:
        return self._ha_sensor_tool

    @staticmethod
    def list_definitions() -> list[dict[str, str]]:
        """Return tool metadata for the frontend."""
        return TOOL_DEFINITIONS
