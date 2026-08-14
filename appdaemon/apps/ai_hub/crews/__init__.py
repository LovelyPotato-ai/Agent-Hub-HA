"""
crews/ — CrewAI Crew Modules
==============================
Each module defines one crew class with a consistent interface:

  class <Name>Crew:
      def __init__(self, llm, **tools): ...
      def kickoff(self, prompt: str, options: dict) -> str: ...

Available crews:
  CodeReviewCrew    — Developer writes code, Reviewer critiques, DevOps commits
  HAAutomationCrew  — NL prompt → HA automation YAML → GitHub commit
  HAAssistantCrew   — Survey sensors → suggest automations → commit top pick
"""

from crews.code_review_crew import CodeReviewCrew
from crews.ha_automation_crew import HAAutomationCrew
from crews.ha_assistant_crew import HAAssistantCrew

__all__ = ["CodeReviewCrew", "HAAutomationCrew", "HAAssistantCrew"]
