"""
tasks.py — CrewAI Task Definitions
=====================================
Defines all tasks used across the three crews.

Tasks are constructed as functions that accept agent instances and runtime
parameters, returning crewai.Task objects.  Context chaining is achieved
via the `context=[previous_task]` parameter — CrewAI automatically injects
the output of context tasks into the current task's prompt.

Task groups:
  Code Review Crew:
    make_write_code_task()       — Developer writes code
    make_review_code_task()      — Reviewer critiques the code
    make_commit_code_task()      — DevOps commits approved code to GitHub

  HA Automation Crew:
    make_read_ha_state_task()    — Read current HA entity states
    make_generate_automation_task() — Generate HA automation YAML
    make_commit_automation_task()   — Commit YAML to GitHub

  HA Assistant Crew:
    make_survey_sensors_task()   — Survey multiple HA sensor states
    make_suggest_automations_task() — Suggest automations from sensor data
    make_apply_automation_task() — Convert suggestions to YAML and commit
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Task


# ===========================================================================
# Code Review Crew Tasks
# ===========================================================================

def make_write_code_task(agent: Agent, prompt: str) -> Task:
    """
    Task 1 of 3 — Developer writes code.

    The agent receives the user's natural language prompt and produces a
    complete, runnable implementation with documentation.
    """
    return Task(
        description=(
            f"Write a complete, production-quality implementation for the "
            f"following request:\n\n"
            f"REQUEST:\n{prompt}\n\n"
            f"Requirements:\n"
            f"- Include all necessary imports\n"
            f"- Add docstrings and type hints\n"
            f"- Include basic error handling\n"
            f"- The code must be immediately runnable without modification\n"
            f"- Do NOT include placeholder comments like '# TODO' or '# implement this'"
        ),
        expected_output=(
            "A complete, runnable code implementation. "
            "Output ONLY the code block — no explanatory prose before or after. "
            "Use a fenced code block with the appropriate language tag "
            "(e.g. ```python ... ```)."
        ),
        agent=agent,
    )


def make_review_code_task(agent: Agent, write_task: Task) -> Task:
    """
    Task 2 of 3 — Reviewer critiques the developer's code.

    Uses `context=[write_task]` so CrewAI injects the developer's output
    into this task's prompt automatically.
    """
    return Task(
        description=(
            "Review the code produced by the Developer agent in the previous task.\n\n"
            "Evaluate it against these criteria:\n"
            "1. Correctness — does it do what was requested?\n"
            "2. Security — any injection, hardcoded secrets, or unsafe operations?\n"
            "3. Performance — any obvious inefficiencies or O(n²) traps?\n"
            "4. Readability — clear variable names, adequate comments?\n"
            "5. Error handling — are edge cases and exceptions handled?\n\n"
            "Provide a structured review with:\n"
            "- A list of specific issues (with line references where possible)\n"
            "- A suggested fix for each issue\n"
            "- A final verdict: APPROVED or NEEDS_REVISION\n\n"
            "If the code is APPROVED, reproduce the final approved version in full."
        ),
        expected_output=(
            "A structured code review containing:\n"
            "1. ISSUES section: numbered list of findings (or 'No issues found')\n"
            "2. VERDICT: either 'APPROVED' or 'NEEDS_REVISION'\n"
            "3. FINAL CODE: the complete, approved code in a fenced code block "
            "(include this even if no changes were needed)"
        ),
        agent=agent,
        context=[write_task],
    )


def make_commit_code_task(agent: Agent, review_task: Task) -> Task:
    """
    Task 3 of 3 — DevOps commits the approved code to GitHub.

    Uses `context=[review_task]` to receive the final approved code.
    The agent must extract the code, choose a filename, write a commit
    message, and call the github_commit tool.
    """
    return Task(
        description=(
            "Take the FINAL CODE from the reviewer's output and commit it to "
            "the GitHub repository.\n\n"
            "Steps:\n"
            "1. Extract the final approved code from the review output\n"
            "2. Determine an appropriate filename based on the code content "
            "(e.g. 'src/utils/yaml_parser.py' for a YAML parser utility)\n"
            "3. Write a conventional commit message "
            "(e.g. 'feat: add YAML parser utility with error handling')\n"
            "4. Call the github_commit tool with filename, content, and commit_message\n"
            "5. Report the result including the commit URL"
        ),
        expected_output=(
            "A confirmation message containing:\n"
            "- The filename used\n"
            "- The commit message\n"
            "- The commit SHA and URL returned by the github_commit tool\n"
            "- Or a clear error message if the commit failed"
        ),
        agent=agent,
        context=[review_task],
    )


# ===========================================================================
# HA Automation Crew Tasks
# ===========================================================================

def make_read_ha_state_task(
    agent: Agent,
    entities: list[str],
    prompt: str,
) -> Task:
    """
    Task 1 of 3 — Read current HA entity states for context.

    Reads the specified entities so the automation generator can make
    context-aware decisions (e.g. knowing the current state of a light
    before writing an automation that controls it).
    """
    entity_list = "\n".join(f"  - {e}" for e in entities) if entities else "  (none specified)"

    return Task(
        description=(
            f"Read the current state of the following Home Assistant entities "
            f"using the ha_sensor_reader tool. This context will be used to "
            f"generate a relevant automation.\n\n"
            f"Entities to read:\n{entity_list}\n\n"
            f"Automation goal (for context): {prompt}\n\n"
            f"For each entity, call ha_sensor_reader and record:\n"
            f"- The entity_id\n"
            f"- The current state value\n"
            f"- Relevant attributes (unit_of_measurement, device_class, etc.)"
        ),
        expected_output=(
            "A summary of all entity states in this format:\n"
            "Entity: <entity_id>\n"
            "State: <value>\n"
            "Key attributes: <relevant attributes>\n\n"
            "Repeat for each entity. If an entity is not found, note it clearly."
        ),
        agent=agent,
    )


def make_generate_automation_task(
    agent: Agent,
    prompt: str,
    read_task: Task,
) -> Task:
    """
    Task 2 of 3 — Generate HA automation YAML from the user's prompt.

    Uses `context=[read_task]` to incorporate current entity states.
    """
    return Task(
        description=(
            f"Generate a complete, valid Home Assistant automation YAML based on "
            f"the following request and the entity states from the previous task.\n\n"
            f"REQUEST:\n{prompt}\n\n"
            f"Requirements for the YAML:\n"
            f"- Must include a unique 'id' field (use a descriptive slug)\n"
            f"- Must include 'alias' and 'description' fields\n"
            f"- Must use the correct HA trigger, condition, and action syntax\n"
            f"- Must be immediately deployable without modification\n"
            f"- Use the entity states from the previous task to make it context-aware\n"
            f"- Include 'mode: single' unless parallel execution is explicitly needed"
        ),
        expected_output=(
            "A complete Home Assistant automation in valid YAML format. "
            "Output ONLY the YAML block — no prose before or after. "
            "Use a fenced code block: ```yaml ... ```"
        ),
        agent=agent,
        context=[read_task],
    )


def make_commit_automation_task(agent: Agent, generate_task: Task) -> Task:
    """
    Task 3 of 3 — Commit the generated automation YAML to GitHub.

    Uses `context=[generate_task]` to receive the YAML content.
    """
    return Task(
        description=(
            "Take the automation YAML from the previous task and commit it to "
            "the GitHub repository.\n\n"
            "Steps:\n"
            "1. Extract the YAML content from the generator's output\n"
            "2. Determine a filename: use 'automations/<automation_id>.yaml' "
            "where <automation_id> matches the 'id' field in the YAML\n"
            "3. Write a commit message: 'feat(automation): <alias from YAML>'\n"
            "4. Call the github_commit tool\n"
            "5. Report the result"
        ),
        expected_output=(
            "A confirmation containing the filename, commit message, "
            "commit SHA, and URL — or a clear error message if it failed."
        ),
        agent=agent,
        context=[generate_task],
    )


# ===========================================================================
# HA Assistant Crew Tasks
# ===========================================================================

def make_survey_sensors_task(
    agent: Agent,
    entities: list[str],
    prompt: str,
) -> Task:
    """
    Task 1 of 3 — Survey multiple HA sensor states.

    Reads all specified entities and builds a comprehensive picture of the
    current home state for the suggestion engine.
    """
    entity_list = "\n".join(f"  - {e}" for e in entities) if entities else "  (none specified)"

    return Task(
        description=(
            f"Survey the current state of the following Home Assistant entities "
            f"using the ha_sensor_reader tool. Build a comprehensive snapshot "
            f"of the home's current state.\n\n"
            f"Entities to survey:\n{entity_list}\n\n"
            f"Analysis goal: {prompt}\n\n"
            f"For each entity:\n"
            f"1. Call ha_sensor_reader to get its current state\n"
            f"2. Note the state value and all relevant attributes\n"
            f"3. Flag any unusual values (e.g. temperature > 30°C, motion at 3am)"
        ),
        expected_output=(
            "A structured home state report:\n"
            "- List of all entities with their current states and key attributes\n"
            "- Any anomalies or notable patterns observed\n"
            "- A brief summary paragraph describing the overall home state"
        ),
        agent=agent,
    )


def make_suggest_automations_task(
    agent: Agent,
    prompt: str,
    survey_task: Task,
) -> Task:
    """
    Task 2 of 3 — Suggest automations based on surveyed sensor data.

    Uses `context=[survey_task]` to analyse the home state snapshot.
    """
    return Task(
        description=(
            f"Based on the home state survey from the previous task, suggest "
            f"practical Home Assistant automations that address the following goal:\n\n"
            f"GOAL: {prompt}\n\n"
            f"For each suggestion:\n"
            f"1. Give it a clear name\n"
            f"2. Explain what it does in plain English (1-2 sentences)\n"
            f"3. Explain WHY it would be beneficial based on the sensor data\n"
            f"4. Provide the complete HA automation YAML\n"
            f"5. Rate the impact: HIGH / MEDIUM / LOW\n\n"
            f"Prioritise suggestions by impact. Aim for 2-4 high-quality "
            f"suggestions rather than many low-quality ones."
        ),
        expected_output=(
            "A numbered list of automation suggestions, each containing:\n"
            "1. Name: <automation name>\n"
            "2. Description: <plain English explanation>\n"
            "3. Rationale: <why this is useful based on the sensor data>\n"
            "4. Impact: HIGH / MEDIUM / LOW\n"
            "5. YAML: ```yaml ... ``` (complete, deployable automation)\n\n"
            "End with a brief summary of the top recommendation."
        ),
        agent=agent,
        context=[survey_task],
    )


def make_apply_automation_task(
    agent: Agent,
    suggest_task: Task,
) -> Task:
    """
    Task 3 of 3 — Commit the top-rated automation suggestion to GitHub.

    Uses `context=[suggest_task]` to receive the suggestions.
    Commits only the highest-impact suggestion to avoid overwhelming the repo.
    """
    return Task(
        description=(
            "From the automation suggestions in the previous task, select the "
            "highest-impact suggestion and commit its YAML to the GitHub repository.\n\n"
            "Steps:\n"
            "1. Identify the suggestion rated HIGH impact (or the first one if none)\n"
            "2. Extract its YAML content\n"
            "3. Determine filename: 'automations/<automation_id>.yaml'\n"
            "4. Write commit message: 'feat(automation): <automation name>'\n"
            "5. Call github_commit tool\n"
            "6. Report which automation was committed and why it was chosen"
        ),
        expected_output=(
            "A report containing:\n"
            "- Which automation was selected and why\n"
            "- The filename and commit message used\n"
            "- The commit SHA and URL — or a clear error if the commit failed"
        ),
        agent=agent,
        context=[suggest_task],
    )
