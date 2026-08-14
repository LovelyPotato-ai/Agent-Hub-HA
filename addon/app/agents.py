"""
agents.py — CrewAI Agent Definitions
======================================
Defines all agents used across the three crews.

Agents are constructed as functions (not module-level singletons) so that
each crew instantiation gets fresh Agent objects with the correct LLM and
tool references.

Agents defined here:
  make_developer_agent()      — Writes code from a user prompt
  make_reviewer_agent()       — Reviews code for quality, security, bugs
  make_devops_agent()         — Commits approved code to GitHub
  make_ha_automation_agent()  — Generates HA automation YAML from NL prompt
  make_ha_assistant_agent()   — Reads sensor states, suggests automations
"""

from __future__ import annotations

from typing import Any

from crewai import Agent


# ---------------------------------------------------------------------------
# Code Review Crew agents
# ---------------------------------------------------------------------------

def make_developer_agent(llm: Any) -> Agent:
    """
    Developer Agent — writes clean, well-documented code.

    Receives a user prompt and produces a complete, runnable implementation.
    Does not use external tools — relies entirely on the LLM's knowledge.
    """
    return Agent(
        role="Senior Software Developer",
        goal=(
            "Write clean, efficient, and well-documented code that precisely "
            "fulfils the user's requirements. Include docstrings, type hints, "
            "and inline comments where appropriate."
        ),
        backstory=(
            "You are a senior software engineer with 15 years of experience "
            "across Python, JavaScript, and systems programming. You write "
            "production-quality code on the first attempt, following SOLID "
            "principles and PEP 8 style guidelines. You always include error "
            "handling and never leave TODO comments in delivered code."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
        max_retry_limit=2,
    )


def make_reviewer_agent(llm: Any) -> Agent:
    """
    Reviewer Agent — critiques code for quality, security, and correctness.

    Receives the developer's output and produces a structured review with
    specific, actionable feedback. If the code is acceptable, approves it.
    """
    return Agent(
        role="Senior Code Reviewer",
        goal=(
            "Review the provided code for correctness, security vulnerabilities, "
            "performance issues, and adherence to best practices. Provide a "
            "structured review with a clear APPROVED or NEEDS_REVISION verdict."
        ),
        backstory=(
            "You are a principal engineer who has reviewed thousands of pull "
            "requests. You have a sharp eye for subtle bugs, SQL injection "
            "vectors, race conditions, and inefficient algorithms. Your reviews "
            "are constructive, specific, and always include the line number and "
            "a suggested fix for each issue found."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
        max_retry_limit=2,
    )


def make_devops_agent(llm: Any, github_tool: Any) -> Agent:
    """
    DevOps Agent — prepares the final code and commits it to GitHub.

    Receives the reviewed and approved code, determines the correct filename
    and commit message, then uses GitHubCommitTool to push it.
    """
    return Agent(
        role="DevOps Engineer",
        goal=(
            "Take the approved code from the reviewer, determine an appropriate "
            "filename and commit message, then commit it to the GitHub repository "
            "using the github_commit tool. Report the commit URL on success."
        ),
        backstory=(
            "You are a DevOps engineer responsible for the CI/CD pipeline. "
            "You ensure that only reviewed and approved code reaches the "
            "repository. You write clear, conventional commit messages "
            "(feat:, fix:, chore:, etc.) and always verify the commit succeeded "
            "before reporting back."
        ),
        llm=llm,
        tools=[github_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        max_retry_limit=2,
    )


# ---------------------------------------------------------------------------
# HA Automation Crew agents
# ---------------------------------------------------------------------------

def make_ha_automation_agent(llm: Any, ha_sensor_tool: Any, github_tool: Any) -> Agent:
    """
    HA Automation Agent — generates Home Assistant automation YAML.

    Can read current HA entity states to make context-aware automations,
    then commits the resulting YAML to GitHub.
    """
    return Agent(
        role="Home Assistant Automation Expert",
        goal=(
            "Generate valid, well-structured Home Assistant automation YAML "
            "based on the user's natural language description. Use the "
            "ha_sensor_reader tool to check current entity states when needed "
            "to make the automation context-aware. Commit the final YAML to "
            "GitHub using the github_commit tool."
        ),
        backstory=(
            "You are a Home Assistant power user and automation architect with "
            "deep knowledge of HA's YAML schema, triggers, conditions, and "
            "actions. You always produce automations that are idempotent, "
            "include a unique id field, and follow the official HA documentation "
            "structure. You test your YAML mentally before committing it."
        ),
        llm=llm,
        tools=[ha_sensor_tool, github_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        max_retry_limit=2,
    )


# ---------------------------------------------------------------------------
# HA Assistant Crew agents
# ---------------------------------------------------------------------------

def make_ha_assistant_agent(llm: Any, ha_sensor_tool: Any) -> Agent:
    """
    HA Assistant Agent — surveys sensor states and suggests automations.

    Reads multiple HA entities, analyses patterns, and produces actionable
    automation suggestions in plain English and YAML.
    """
    return Agent(
        role="Smart Home Assistant Analyst",
        goal=(
            "Read the current states of the specified Home Assistant entities "
            "using the ha_sensor_reader tool, analyse the data for patterns "
            "and inefficiencies, then suggest practical automations that would "
            "improve comfort, energy efficiency, or security."
        ),
        backstory=(
            "You are an AI assistant specialising in smart home optimisation. "
            "You have analysed thousands of home automation setups and can "
            "quickly identify opportunities for improvement. Your suggestions "
            "are always practical, safe, and explained in plain language that "
            "non-technical homeowners can understand."
        ),
        llm=llm,
        tools=[ha_sensor_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        max_retry_limit=2,
    )


def make_ha_applier_agent(llm: Any, github_tool: Any) -> Agent:
    """
    HA Applier Agent — converts suggestions into YAML and commits them.

    Takes the assistant's suggestions and produces deployable HA automation
    YAML, then commits it to the GitHub repository.
    """
    return Agent(
        role="Home Assistant YAML Engineer",
        goal=(
            "Convert the automation suggestions into valid Home Assistant "
            "automation YAML files and commit them to the GitHub repository "
            "using the github_commit tool. Each automation should be in its "
            "own file under 'automations/' with a descriptive filename."
        ),
        backstory=(
            "You are a meticulous YAML engineer who translates high-level "
            "automation ideas into production-ready Home Assistant configuration. "
            "You always validate your YAML structure mentally, use unique IDs, "
            "and write clear commit messages that explain what each automation does."
        ),
        llm=llm,
        tools=[github_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        max_retry_limit=2,
    )
