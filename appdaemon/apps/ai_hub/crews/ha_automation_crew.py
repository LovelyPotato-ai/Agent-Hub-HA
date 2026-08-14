"""
ha_automation_crew.py — HA Automation Crew
============================================
A three-task sequential crew that converts a natural language prompt into
a deployable Home Assistant automation YAML and commits it to GitHub.

Pipeline:
  1. HA Automation Agent reads current entity states (context-awareness)
  2. HA Automation Agent generates the automation YAML
  3. HA Automation Agent commits the YAML to GitHub

Note: All three tasks are handled by a single HA Automation Agent that has
both ha_sensor_reader and github_commit tools available.  This keeps the
crew lightweight while still providing full capability.

Usage (via crew_router.py):
  crew = HAAutomationCrew(
      llm=llm,
      github_tool=github_tool,
      ha_sensor_tool=ha_sensor_tool,
  )
  result = crew.kickoff(
      prompt="Turn off all lights when everyone leaves home",
      options={"entities_to_read": ["person.john", "light.living_room"]},
  )
"""

from __future__ import annotations

import logging
from typing import Any

from crewai import Crew, Process

from agents import make_ha_automation_agent
from tasks import (
    make_commit_automation_task,
    make_generate_automation_task,
    make_read_ha_state_task,
)

logger = logging.getLogger("ai_hub")


class HAAutomationCrew:
    """
    NL prompt → HA automation YAML → GitHub commit crew.

    Args:
        llm:            LangChain chat model instance
        github_tool:    GitHubCommitTool instance
        ha_sensor_tool: HASensorReaderTool instance
    """

    def __init__(
        self,
        llm: Any,
        github_tool: Any,
        ha_sensor_tool: Any,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._github_tool = github_tool
        self._ha_sensor_tool = ha_sensor_tool

    def build(self, prompt: str, entities_to_read: list[str]) -> Crew:
        """
        Construct the Crew object.
        Called fresh for each kickoff to avoid state leakage.
        """
        # Single agent with both tools
        automation_agent = make_ha_automation_agent(
            llm=self._llm,
            ha_sensor_tool=self._ha_sensor_tool,
            github_tool=self._github_tool,
        )

        # Tasks
        read_task = make_read_ha_state_task(
            agent=automation_agent,
            entities=entities_to_read,
            prompt=prompt,
        )
        generate_task = make_generate_automation_task(
            agent=automation_agent,
            prompt=prompt,
            read_task=read_task,
        )
        commit_task = make_commit_automation_task(
            agent=automation_agent,
            generate_task=generate_task,
        )

        return Crew(
            agents=[automation_agent],
            tasks=[read_task, generate_task, commit_task],
            process=Process.sequential,
            verbose=True,
            memory=False,
            cache=True,
        )

    def kickoff(self, prompt: str, options: dict[str, Any] | None = None) -> str:
        """
        Build and run the crew.

        Args:
            prompt:  Natural language description of the desired automation.
            options: Optional dict with key 'entities_to_read' (list of entity IDs
                     to read for context before generating the automation).

        Returns:
            The final output string (commit confirmation or error message).
        """
        opts = options or {}
        entities_to_read: list[str] = opts.get("entities_to_read", [])

        logger.info(
            "HAAutomationCrew kickoff: prompt='%s…', entities=%s",
            prompt[:80],
            entities_to_read,
        )

        crew = self.build(prompt=prompt, entities_to_read=entities_to_read)
        result = crew.kickoff()
        return str(result)
