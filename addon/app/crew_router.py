"""
crew_router.py — Runtime Crew Selector
========================================
Dispatches an incoming trigger payload to the correct crew class based on
the 'crew' field in the payload.

This is the single entry point called by AIHubOrchestrator._run_crew_sync().
Adding a new crew requires only:
  1. Creating a new crew module in crews/
  2. Adding it to CREW_MAP below

CREW_MAP keys are the valid values for the 'crew' field in the trigger payload:
  { "crew": "code_review",   "prompt": "...", "options": {} }
  { "crew": "ha_automation", "prompt": "...", "options": {"entities_to_read": [...]} }
  { "crew": "ha_assistant",  "prompt": "...", "options": {"entities_to_survey": [...]} }
"""

from __future__ import annotations

import logging
from typing import Any

from crews.code_review_crew import CodeReviewCrew
from crews.ha_assistant_crew import HAAssistantCrew
from crews.ha_automation_crew import HAAutomationCrew

logger = logging.getLogger("ai_hub")

# ---------------------------------------------------------------------------
# Crew registry
# ---------------------------------------------------------------------------
# Maps the 'crew' field value in the trigger payload to the crew class.
# Each class must implement: kickoff(prompt: str, options: dict) -> str
CREW_MAP: dict[str, type] = {
    "code_review":   CodeReviewCrew,
    "ha_automation": HAAutomationCrew,
    "ha_assistant":  HAAssistantCrew,
}


def get_available_crews() -> list[str]:
    """Return the list of valid crew names for validation and UI display."""
    return sorted(CREW_MAP.keys())


def route(
    payload: dict[str, Any],
    llm: Any,
    tools: dict[str, Any],
) -> str:
    """
    Validate the payload, instantiate the correct crew, and run it.

    Args:
        payload: Dict with keys:
                   'crew'    (str)  — crew name, must be in CREW_MAP
                   'prompt'  (str)  — user's natural language request
                   'options' (dict) — crew-specific options (may be empty)
        llm:     LangChain chat model instance from llm_factory.get_llm()
        tools:   Dict of tool instances:
                   'github_tool'    — GitHubCommitTool
                   'ha_sensor_tool' — HASensorReaderTool

    Returns:
        The crew's final output as a string.

    Raises:
        ValueError: If 'crew' is missing or not in CREW_MAP.
        ValueError: If 'prompt' is missing or empty.
    """
    # ── Validate crew name ─────────────────────────────────────────────
    crew_name: str = payload.get("crew", "").strip()
    if not crew_name:
        raise ValueError(
            "Trigger payload is missing the 'crew' field. "
            f"Valid values: {get_available_crews()}"
        )
    if crew_name not in CREW_MAP:
        raise ValueError(
            f"Unknown crew: '{crew_name}'. "
            f"Valid values: {get_available_crews()}"
        )

    # ── Validate prompt ────────────────────────────────────────────────
    prompt: str = payload.get("prompt", "").strip()
    if not prompt:
        raise ValueError(
            "Trigger payload is missing the 'prompt' field. "
            "Provide a non-empty natural language request."
        )

    options: dict[str, Any] = payload.get("options", {}) or {}

    # ── Instantiate crew ───────────────────────────────────────────────
    crew_class = CREW_MAP[crew_name]
    logger.info(
        "Routing to %s (prompt='%s…')",
        crew_class.__name__,
        prompt[:60],
    )

    crew_instance = crew_class(llm=llm, **tools)

    # ── Run ────────────────────────────────────────────────────────────
    result: str = crew_instance.kickoff(prompt=prompt, options=options)

    logger.info(
        "%s completed. Result length: %d chars.",
        crew_class.__name__,
        len(result),
    )
    return result
