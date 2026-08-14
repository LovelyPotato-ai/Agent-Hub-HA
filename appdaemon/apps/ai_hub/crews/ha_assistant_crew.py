"""
ha_assistant_crew.py — HA Assistant Crew
==========================================
A three-task sequential crew that surveys Home Assistant sensor states,
suggests practical automations, and commits the top recommendation to GitHub.

Pipeline:
  1. HA Assistant Agent surveys specified entity states
  2. HA Assistant Agent suggests automations based on the survey
  3. HA Applier Agent converts the top suggestion to YAML and commits it

Usage (via crew_router.py):
  crew = HAAssistantCrew(
      llm=llm,
      github_tool=github_tool,
      ha_sensor_tool=ha_sensor_tool,
  )
  result = crew.kickoff(
      prompt="Suggest energy-saving automations",
      options={
          "entities_to_survey": [
              "sensor.living_room_temperature",
              "switch.living_room_ac",
          ]
      },
  )
"""

from __future__ import annotations

import logging
from typing import Any

from crewai import Crew, Process

from agents import make_ha_applier_agent, make_ha_assistant_agent
from tasks import (
    make_apply_automation_task,
    make_suggest_automations_task,
    make_survey_sensors_task,
)

logger = logging.getLogger("ai_hub")


class HAAssistantCrew:
    """
    Sensor survey → automation suggestions → GitHub commit crew.

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

    def build(self, prompt: str, entities_to_survey: list[str]) -> Crew:
        """
        Construct the Crew object.
        Called fresh for each kickoff to avoid state leakage.
        """
        # Two agents: assistant (reads + suggests) and applier (commits)
        assistant_agent = make_ha_assistant_agent(
            llm=self._llm,
            ha_sensor_tool=self._ha_sensor_tool,
        )
        applier_agent = make_ha_applier_agent(
            llm=self._llm,
            github_tool=self._github_tool,
        )

        # Tasks
        survey_task = make_survey_sensors_task(
            agent=assistant_agent,
            entities=entities_to_survey,
            prompt=prompt,
        )
        suggest_task = make_suggest_automations_task(
            agent=assistant_agent,
            prompt=prompt,
            survey_task=survey_task,
        )
        apply_task = make_apply_automation_task(
            agent=applier_agent,
            suggest_task=suggest_task,
        )

        return Crew(
            agents=[assistant_agent, applier_agent],
            tasks=[survey_task, suggest_task, apply_task],
            process=Process.sequential,
            verbose=True,
            memory=False,
            cache=True,
        )

    def kickoff(self, prompt: str, options: dict[str, Any] | None = None) -> str:
        """
        Build and run the crew.

        Args:
            prompt:  Goal for the automation suggestions (e.g. 'save energy').
            options: Optional dict with key 'entities_to_survey' (list of
                     entity IDs to read before generating suggestions).

        Returns:
            The final output string (commit confirmation or suggestions report).
        """
        opts = options or {}
        entities_to_survey: list[str] = opts.get("entities_to_survey", [])

        logger.info(
            "HAAssistantCrew kickoff: prompt='%s…', entities=%s",
            prompt[:80],
            entities_to_survey,
        )

        crew = self.build(prompt=prompt, entities_to_survey=entities_to_survey)
        result = crew.kickoff()
        return str(result)
