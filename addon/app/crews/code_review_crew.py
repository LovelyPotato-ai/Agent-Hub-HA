"""
code_review_crew.py — Code Review Crew
========================================
A three-agent sequential crew:

  1. Developer Agent   → writes code from the user's prompt
  2. Reviewer Agent    → critiques the code and produces a verdict
  3. DevOps Agent      → commits the approved code to GitHub

The crew uses CrewAI's sequential process so each agent's output is
automatically passed as context to the next task.

Usage (via crew_router.py):
  crew = CodeReviewCrew(llm=llm, github_tool=github_tool)
  result = crew.kickoff(prompt="Write a YAML parser utility", options={})
"""

from __future__ import annotations

import logging
from typing import Any

from crewai import Crew, Process

from agents import make_developer_agent, make_devops_agent, make_reviewer_agent
from tasks import make_commit_code_task, make_review_code_task, make_write_code_task

logger = logging.getLogger("ai_hub")


class CodeReviewCrew:
    """
    Developer → Reviewer → DevOps sequential crew.

    Args:
        llm:         LangChain chat model instance from llm_factory.get_llm()
        github_tool: GitHubCommitTool instance from tools.py
    """

    def __init__(self, llm: Any, github_tool: Any, **kwargs: Any) -> None:
        self._llm = llm
        self._github_tool = github_tool

    def build(self, prompt: str) -> Crew:
        """
        Construct the Crew object with agents and tasks wired together.
        Called fresh for each kickoff so there is no state leakage between runs.
        """
        # ── Agents ────────────────────────────────────────────────────
        developer = make_developer_agent(llm=self._llm)
        reviewer = make_reviewer_agent(llm=self._llm)
        devops = make_devops_agent(llm=self._llm, github_tool=self._github_tool)

        # ── Tasks (sequential — each uses the previous as context) ────
        write_task = make_write_code_task(agent=developer, prompt=prompt)
        review_task = make_review_code_task(agent=reviewer, write_task=write_task)
        commit_task = make_commit_code_task(agent=devops, review_task=review_task)

        return Crew(
            agents=[developer, reviewer, devops],
            tasks=[write_task, review_task, commit_task],
            process=Process.sequential,
            verbose=True,
            # Memory disabled — keeps the container lightweight on HA Green
            memory=False,
            # Cache tool results within a single run
            cache=True,
        )

    def kickoff(self, prompt: str, options: dict[str, Any] | None = None) -> str:
        """
        Build and run the crew.

        Args:
            prompt:  The user's code request.
            options: Unused for this crew; reserved for future extensions.

        Returns:
            The final output string from the DevOps agent (commit confirmation
            or error message).
        """
        logger.info("CodeReviewCrew kickoff: prompt='%s…'", prompt[:80])
        crew = self.build(prompt=prompt)
        result = crew.kickoff()
        # CrewAI returns a CrewOutput object; convert to string
        return str(result)
