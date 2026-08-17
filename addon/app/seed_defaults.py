"""
seed_defaults.py — Default Agents and Workflows
=================================================
Seeds the 3 original hardcoded crews as editable workflow definitions
on first run. Uses upsert so existing user data is never overwritten.

Called once at orchestrator startup before the server begins accepting requests.
"""

from __future__ import annotations

import logging

from agent_registry import upsert_agent
from workflow_registry import upsert_workflow

logger = logging.getLogger("ai_hub.seed_defaults")

# ---------------------------------------------------------------------------
# Default agent IDs (stable UUIDs so upsert never duplicates)
# ---------------------------------------------------------------------------

_DEVELOPER_ID    = "00000000-0000-0000-0000-000000000001"
_REVIEWER_ID     = "00000000-0000-0000-0000-000000000002"
_DEVOPS_ID       = "00000000-0000-0000-0000-000000000003"
_HA_AUTO_ID      = "00000000-0000-0000-0000-000000000004"
_HA_ASSISTANT_ID = "00000000-0000-0000-0000-000000000005"
_HA_APPLIER_ID   = "00000000-0000-0000-0000-000000000006"

# ---------------------------------------------------------------------------
# Default workflow IDs
# ---------------------------------------------------------------------------

_CODE_REVIEW_WF_ID  = "00000000-0000-0000-0001-000000000001"
_HA_AUTOMATION_WF_ID = "00000000-0000-0000-0001-000000000002"
_HA_ASSISTANT_WF_ID  = "00000000-0000-0000-0001-000000000003"


def seed() -> None:
    """Seed default agents and workflows. Safe to call multiple times."""
    logger.info("Seeding default agents and workflows…")
    _seed_agents()
    _seed_workflows()
    logger.info("Default seed complete.")


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def _seed_agents() -> None:
    upsert_agent({
        "id": _DEVELOPER_ID,
        "name": "Senior Developer",
        "role": "Senior Software Developer",
        "goal": (
            "Write clean, efficient, and well-documented code that precisely "
            "fulfils the user's requirements. Include docstrings, type hints, "
            "and inline comments where appropriate."
        ),
        "backstory": (
            "You are a senior software engineer with 15 years of experience "
            "across Python, JavaScript, and systems programming. You write "
            "production-quality code on the first attempt, following SOLID "
            "principles and PEP 8 style guidelines. You always include error "
            "handling and never leave TODO comments in delivered code."
        ),
        "tools": [],
        "allow_delegation": False,
        "max_iter": 3,
    })

    upsert_agent({
        "id": _REVIEWER_ID,
        "name": "Code Reviewer",
        "role": "Senior Code Reviewer",
        "goal": (
            "Review the provided code for correctness, security vulnerabilities, "
            "performance issues, and adherence to best practices. Provide a "
            "structured review with a clear APPROVED or NEEDS_REVISION verdict."
        ),
        "backstory": (
            "You are a principal engineer who has reviewed thousands of pull "
            "requests. You have a sharp eye for subtle bugs, SQL injection "
            "vectors, race conditions, and inefficient algorithms. Your reviews "
            "are constructive, specific, and always include the line number and "
            "a suggested fix for each issue found."
        ),
        "tools": [],
        "allow_delegation": False,
        "max_iter": 3,
    })

    upsert_agent({
        "id": _DEVOPS_ID,
        "name": "DevOps Engineer",
        "role": "DevOps Engineer",
        "goal": (
            "Commit the reviewed and approved code to the GitHub repository "
            "with a clear, descriptive commit message."
        ),
        "backstory": (
            "You are a DevOps engineer responsible for maintaining the codebase. "
            "You only commit code that has been explicitly approved by the reviewer. "
            "You write clear commit messages following conventional commits format."
        ),
        "tools": ["github_commit"],
        "allow_delegation": False,
        "max_iter": 3,
    })

    upsert_agent({
        "id": _HA_AUTO_ID,
        "name": "HA Automation Generator",
        "role": "Home Assistant Automation Expert",
        "goal": (
            "Generate valid Home Assistant automation YAML from a natural language "
            "description. The YAML must be immediately usable in configuration.yaml."
        ),
        "backstory": (
            "You are an expert in Home Assistant automations with deep knowledge "
            "of the HA YAML schema, triggers, conditions, and actions. You always "
            "produce valid, well-commented YAML that follows HA best practices."
        ),
        "tools": ["ha_sensor_reader"],
        "allow_delegation": False,
        "max_iter": 5,
    })

    upsert_agent({
        "id": _HA_ASSISTANT_ID,
        "name": "HA Sensor Analyst",
        "role": "Home Assistant Sensor Analyst",
        "goal": (
            "Survey the current state of Home Assistant sensors and suggest "
            "useful automations based on the observed patterns."
        ),
        "backstory": (
            "You are a smart home consultant who analyses sensor data to identify "
            "automation opportunities. You look for patterns like lights left on, "
            "temperature anomalies, and motion patterns to suggest practical automations."
        ),
        "tools": ["ha_sensor_reader"],
        "allow_delegation": False,
        "max_iter": 5,
    })

    upsert_agent({
        "id": _HA_APPLIER_ID,
        "name": "HA Automation Committer",
        "role": "Home Assistant Automation Committer",
        "goal": (
            "Convert the suggested automation into valid HA YAML and commit it "
            "to the GitHub repository."
        ),
        "backstory": (
            "You are a Home Assistant expert who translates automation suggestions "
            "into production-ready YAML and commits them to the repository."
        ),
        "tools": ["github_commit"],
        "allow_delegation": False,
        "max_iter": 3,
    })


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

def _seed_workflows() -> None:
    # ── Code Review Workflow ──────────────────────────────────────────────
    upsert_workflow({
        "id": _CODE_REVIEW_WF_ID,
        "name": "Code Review",
        "description": "Developer writes code → Reviewer critiques → DevOps commits to GitHub",
        "process": "sequential",
        "tasks": [
            {
                "id": "cr-task-1",
                "name": "Write Code",
                "description": (
                    "Write a complete, production-quality implementation for the "
                    "following request:\n\n{prompt}\n\n"
                    "Requirements:\n"
                    "- Include all necessary imports\n"
                    "- Add docstrings and type hints\n"
                    "- Include basic error handling\n"
                    "- The code must be immediately runnable without modification"
                ),
                "agent_id": _DEVELOPER_ID,
                "expected_output": "A complete, runnable code implementation.",
                "depends_on": [],
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "cr-task-2",
                "name": "Review Code",
                "description": (
                    "Review the code written by the developer. Check for:\n"
                    "- Correctness and completeness\n"
                    "- Security vulnerabilities\n"
                    "- Performance issues\n"
                    "- Code style and best practices\n\n"
                    "Provide a structured review with APPROVED or NEEDS_REVISION verdict."
                ),
                "agent_id": _REVIEWER_ID,
                "expected_output": "A structured code review with verdict.",
                "depends_on": ["cr-task-1"],
                "position": {"x": 400, "y": 200},
            },
            {
                "id": "cr-task-3",
                "name": "Commit to GitHub",
                "description": (
                    "If the code was APPROVED by the reviewer, commit it to GitHub. "
                    "Use a descriptive filename and commit message. "
                    "If NEEDS_REVISION, report the issues without committing."
                ),
                "agent_id": _DEVOPS_ID,
                "expected_output": "GitHub commit confirmation or revision report.",
                "depends_on": ["cr-task-2"],
                "position": {"x": 700, "y": 200},
            },
        ],
    })

    # ── HA Automation Workflow ────────────────────────────────────────────
    upsert_workflow({
        "id": _HA_AUTOMATION_WF_ID,
        "name": "HA Automation",
        "description": "Natural language → HA automation YAML → GitHub commit",
        "process": "sequential",
        "tasks": [
            {
                "id": "ha-auto-task-1",
                "name": "Generate Automation YAML",
                "description": (
                    "Generate a complete Home Assistant automation YAML for:\n\n{prompt}\n\n"
                    "The YAML must be valid and immediately usable in configuration.yaml. "
                    "Include comments explaining each section."
                ),
                "agent_id": _HA_AUTO_ID,
                "expected_output": "Valid HA automation YAML with comments.",
                "depends_on": [],
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "ha-auto-task-2",
                "name": "Commit Automation",
                "description": (
                    "Commit the generated automation YAML to GitHub. "
                    "Save it as 'automations/<descriptive_name>.yaml'."
                ),
                "agent_id": _DEVOPS_ID,
                "expected_output": "GitHub commit confirmation.",
                "depends_on": ["ha-auto-task-1"],
                "position": {"x": 400, "y": 200},
            },
        ],
    })

    # ── HA Assistant Workflow ─────────────────────────────────────────────
    upsert_workflow({
        "id": _HA_ASSISTANT_WF_ID,
        "name": "HA Assistant",
        "description": "Survey sensors → suggest automations → commit top pick",
        "process": "sequential",
        "tasks": [
            {
                "id": "ha-asst-task-1",
                "name": "Survey Sensors",
                "description": (
                    "Read the current state of Home Assistant sensors and entities. "
                    "Focus on: {prompt}\n\n"
                    "Summarise what you observe and identify patterns or anomalies."
                ),
                "agent_id": _HA_ASSISTANT_ID,
                "expected_output": "A summary of sensor states and observed patterns.",
                "depends_on": [],
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "ha-asst-task-2",
                "name": "Suggest Automations",
                "description": (
                    "Based on the sensor survey, suggest 3-5 practical automations "
                    "that would improve comfort, energy efficiency, or security. "
                    "Rank them by impact and ease of implementation."
                ),
                "agent_id": _HA_ASSISTANT_ID,
                "expected_output": "A ranked list of automation suggestions with rationale.",
                "depends_on": ["ha-asst-task-1"],
                "position": {"x": 400, "y": 200},
            },
            {
                "id": "ha-asst-task-3",
                "name": "Commit Top Automation",
                "description": (
                    "Take the top-ranked automation suggestion and convert it to "
                    "valid HA YAML, then commit it to GitHub."
                ),
                "agent_id": _HA_APPLIER_ID,
                "expected_output": "GitHub commit confirmation with the automation YAML.",
                "depends_on": ["ha-asst-task-2"],
                "position": {"x": 700, "y": 200},
            },
        ],
    })
