"""
crew_executor.py — Dynamic DAG Crew Executor
=============================================
Builds and executes CrewAI crews from dynamic workflow definitions.

Execution modes:
  sequential   — tasks run in dependency order, each gets previous output as context
  hierarchical — a manager LLM orchestrates agents with full delegation
  dag          — topological sort with parallel execution of independent branches

The executor:
  1. Loads the workflow and agent definitions
  2. Resolves tool IDs to CrewAI tool instances
  3. Builds CrewAI Agent and Task objects
  4. Executes the crew (sequential/hierarchical) or DAG engine (dag)
  5. Returns the final result string
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict, deque
from concurrent.futures import Executor
from typing import Any

from crewai import Agent, Crew, Process, Task

from agent_registry import get_agent
from llm_factory import get_llm, get_llm_from_provider_def
from tool_factory import ToolFactory
from workflow_registry import get_workflow

logger = logging.getLogger("ai_hub.crew_executor")


# ---------------------------------------------------------------------------
# LLM resolution
# ---------------------------------------------------------------------------

def _resolve_llm(llm_override: dict[str, Any] | None, default_llm: Any) -> Any:
    """
    Return the LLM to use for an agent.
    If llm_override is set, build a new LLM from it; otherwise use the default.
    """
    if not llm_override:
        return default_llm
    provider = llm_override.get("provider", "openai")
    model = llm_override.get("model", "gpt-4o")
    try:
        # Resolve via provider registry (supports custom providers)
        from provider_registry import get_provider
        provider_def = get_provider(provider)
        if provider_def:
            api_key = os.environ.get(provider_def.get("api_key_field", ""), "")
            return get_llm_from_provider_def(
                provider_def=provider_def,
                model=model,
                api_key=api_key,
            )
        # Legacy fallback
        api_keys = {
            "openai":     os.environ.get("AI_HUB_OPENAI_KEY", ""),
            "gemini":     os.environ.get("AI_HUB_GEMINI_KEY", ""),
            "anthropic":  os.environ.get("AI_HUB_ANTHROPIC_KEY", ""),
            "openrouter": os.environ.get("AI_HUB_OPENROUTER_KEY", ""),
        }
        return get_llm(
            provider=provider,
            model=model,
            api_key=api_keys.get(provider, ""),
        )
    except Exception as exc:
        logger.warning("Failed to build override LLM (%s/%s): %s — using default", provider, model, exc)
        return default_llm


# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------

def _build_crewai_agent(
    agent_def: dict[str, Any],
    tool_factory: ToolFactory,
    default_llm: Any,
    allow_delegation_override: bool | None = None,
    github_repo_id: str = "",
) -> Agent:
    """Build a CrewAI Agent from an agent definition dict."""
    llm = _resolve_llm(agent_def.get("llm_override"), default_llm)
    tool_ids = list(agent_def.get("tools", []))
    tools = tool_factory.get_tools([t for t in tool_ids if t != "github_commit"])
    if "github_commit" in tool_ids:
        tools.append(tool_factory.get_github_tool_for_repo(github_repo_id))
    allow_delegation = (
        allow_delegation_override
        if allow_delegation_override is not None
        else bool(agent_def.get("allow_delegation", False))
    )
    return Agent(
        role=agent_def["role"],
        goal=agent_def["goal"],
        backstory=agent_def["backstory"],
        llm=llm,
        tools=tools,
        verbose=True,
        allow_delegation=allow_delegation,
        max_iter=int(agent_def.get("max_iter", 5)),
        max_retry_limit=2,
    )


# ---------------------------------------------------------------------------
# Task builder
# ---------------------------------------------------------------------------

def _build_crewai_task(
    task_def: dict[str, Any],
    agent: Agent,
    prompt: str,
    context_tasks: list[Task] | None = None,
) -> Task:
    """
    Build a CrewAI Task from a task definition dict.
    {prompt} in the description is replaced with the user's prompt.
    """
    description = task_def["description"].replace("{prompt}", prompt)
    return Task(
        description=description,
        expected_output=task_def.get("expected_output", "Task output"),
        agent=agent,
        context=context_tasks or [],
    )


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

def _topological_levels(tasks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """
    Return tasks grouped into execution levels via Kahn's algorithm.
    Tasks in the same level have no dependencies on each other and can run in parallel.

    Example:
      Level 0: [t1, t2]       (no dependencies)
      Level 1: [t3]           (depends on t1)
      Level 2: [t4]           (depends on t2, t3)
    """
    task_map = {t["id"]: t for t in tasks}
    in_degree: dict[str, int] = {t["id"]: 0 for t in tasks}
    dependents: dict[str, list[str]] = defaultdict(list)

    for task in tasks:
        for dep_id in task.get("depends_on", []):
            in_degree[task["id"]] += 1
            dependents[dep_id].append(task["id"])

    queue: deque[str] = deque(
        task_id for task_id, deg in in_degree.items() if deg == 0
    )
    levels: list[list[dict[str, Any]]] = []

    while queue:
        level_size = len(queue)
        level: list[dict[str, Any]] = []
        for _ in range(level_size):
            task_id = queue.popleft()
            level.append(task_map[task_id])
            for dependent_id in dependents[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)
        levels.append(level)

    # If not all tasks were processed, the graph has a cycle
    processed = sum(len(lvl) for lvl in levels)
    if processed != len(tasks):
        raise ValueError(
            "Workflow task graph contains a cycle — cannot execute. "
            "Check 'depends_on' references for circular dependencies."
        )

    return levels


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

class CrewExecutor:
    """
    Executes a workflow definition as a CrewAI crew.

    Usage:
        executor = CrewExecutor(tool_factory=factory, default_llm=llm)
        result = await executor.run_workflow(workflow_id, prompt="...")
        result = await executor.run_agent(agent_id, prompt="...")
    """

    def __init__(
        self,
        tool_factory: ToolFactory,
        default_llm: Any,
        kickoff_executor: Executor | None = None,
    ) -> None:
        self._tool_factory = tool_factory
        self._default_llm = default_llm
        # Executor used for crew.kickoff() calls.  When CrewExecutor.run_*
        # is itself called via run_coroutine_threadsafe from a worker thread,
        # using the *same* thread pool for kickoff would deadlock.  Pass a
        # dedicated executor to avoid that.
        self._kickoff_executor = kickoff_executor

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def run_workflow(self, workflow_id: str, prompt: str) -> str:
        """
        Execute a workflow by ID.
        Returns the final result string.
        Raises ValueError if workflow or any referenced agent is not found.
        """
        workflow = get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        process = workflow.get("process", "sequential")
        tasks_def = workflow.get("tasks", [])

        if not tasks_def:
            raise ValueError(f"Workflow '{workflow['name']}' has no tasks")

        logger.info(
            "Executing workflow '%s' (process=%s, tasks=%d)",
            workflow["name"], process, len(tasks_def),
        )

        if process == "dag":
            return await self._run_dag(tasks_def, prompt, workflow)
        elif process == "hierarchical":
            return await self._run_hierarchical(tasks_def, prompt, workflow)
        else:
            # sequential (default)
            return await self._run_sequential(tasks_def, prompt)

    async def run_agent(self, agent_id: str, prompt: str) -> str:
        """
        Run a single agent as a one-task crew.
        Returns the agent's output string.
        """
        agent_def = get_agent(agent_id)
        if not agent_def:
            raise ValueError(f"Agent '{agent_id}' not found")

        logger.info("Running single agent '%s'", agent_def["name"])

        agent = _build_crewai_agent(agent_def, self._tool_factory, self._default_llm)
        task = Task(
            description=prompt,
            expected_output="Agent response to the prompt",
            agent=agent,
        )
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
            memory=False,
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self._kickoff_executor, lambda: crew.kickoff())
        return str(result)

    # ------------------------------------------------------------------
    # Sequential execution
    # ------------------------------------------------------------------

    async def _run_sequential(
        self,
        tasks_def: list[dict[str, Any]],
        prompt: str,
    ) -> str:
        """
        Run tasks in dependency order (topological sort).
        Each task gets all its dependency tasks as context.
        """
        levels = _topological_levels(tasks_def)
        task_map_def = {t["id"]: t for t in tasks_def}

        # Build all CrewAI agents and tasks upfront
        crewai_agents: dict[str, Agent] = {}
        crewai_tasks: dict[str, Task] = {}

        # We need to build tasks in topological order so context refs are valid
        for level in levels:
            for task_def in level:
                agent_id = task_def.get("agent_id", "")
                agent_def = get_agent(agent_id)
                if not agent_def:
                    raise ValueError(
                        f"Task '{task_def['name']}' references unknown agent '{agent_id}'"
                    )
                if agent_id not in crewai_agents:
                    crewai_agents[agent_id] = _build_crewai_agent(
                        agent_def, self._tool_factory, self._default_llm,
                        github_repo_id=task_def.get("github_repo_id", ""),
                    )
                context_tasks = [
                    crewai_tasks[dep_id]
                    for dep_id in task_def.get("depends_on", [])
                    if dep_id in crewai_tasks
                ]
                crewai_tasks[task_def["id"]] = _build_crewai_task(
                    task_def,
                    crewai_agents[agent_id],
                    prompt,
                    context_tasks,
                )

        # Flatten tasks in topological order for the Crew
        ordered_tasks = [
            crewai_tasks[task_def["id"]]
            for level in levels
            for task_def in level
        ]
        all_agents = list(crewai_agents.values())

        crew = Crew(
            agents=all_agents,
            tasks=ordered_tasks,
            process=Process.sequential,
            verbose=True,
            memory=False,
            cache=True,
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self._kickoff_executor, lambda: crew.kickoff())
        return str(result)

    # ------------------------------------------------------------------
    # DAG execution (parallel branches)
    # ------------------------------------------------------------------

    async def _run_dag(
        self,
        tasks_def: list[dict[str, Any]],
        prompt: str,
        workflow: dict[str, Any],
    ) -> str:
        """
        Execute tasks as a true DAG with parallel independent branches.

        Algorithm:
          1. Topological sort into levels
          2. For each level, run all tasks in parallel (asyncio.gather)
          3. Each task's output is stored and injected as context for dependents
          4. Return the output of the last level's tasks (merged if multiple)
        """
        levels = _topological_levels(tasks_def)
        task_map_def = {t["id"]: t for t in tasks_def}
        task_outputs: dict[str, str] = {}  # task_id → output string

        for level_idx, level in enumerate(levels):
            logger.info(
                "DAG level %d/%d: running %d task(s) in parallel",
                level_idx + 1, len(levels), len(level),
            )
            # Run all tasks in this level concurrently
            coros = [
                self._run_single_task_with_context(
                    task_def, prompt, task_outputs
                )
                for task_def in level
            ]
            results = await asyncio.gather(*coros)
            for task_def, result in zip(level, results):
                task_outputs[task_def["id"]] = result

        # Return the output of the final level (or merge if multiple)
        final_level = levels[-1]
        if len(final_level) == 1:
            return task_outputs[final_level[0]["id"]]
        # Multiple final tasks — concatenate their outputs
        parts = []
        for task_def in final_level:
            parts.append(f"[{task_def['name']}]\n{task_outputs[task_def['id']]}")
        return "\n\n---\n\n".join(parts)

    async def _run_single_task_with_context(
        self,
        task_def: dict[str, Any],
        prompt: str,
        task_outputs: dict[str, str],
    ) -> str:
        """Run a single task as a 1-agent crew, injecting dependency outputs as context."""
        agent_id = task_def.get("agent_id", "")
        agent_def = get_agent(agent_id)
        if not agent_def:
            raise ValueError(
                f"Task '{task_def['name']}' references unknown agent '{agent_id}'"
            )

        agent = _build_crewai_agent(
            agent_def, self._tool_factory, self._default_llm,
            github_repo_id=task_def.get("github_repo_id", ""),
        )

        # Build description with context from dependencies
        description = task_def["description"].replace("{prompt}", prompt)
        dep_context = ""
        for dep_id in task_def.get("depends_on", []):
            if dep_id in task_outputs:
                dep_context += f"\n\nContext from previous task:\n{task_outputs[dep_id]}"
        if dep_context:
            description = description + dep_context

        task = Task(
            description=description,
            expected_output=task_def.get("expected_output", "Task output"),
            agent=agent,
        )
        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
            memory=False,
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self._kickoff_executor, lambda: crew.kickoff())
        return str(result)

    # ------------------------------------------------------------------
    # Hierarchical execution
    # ------------------------------------------------------------------

    async def _run_hierarchical(
        self,
        tasks_def: list[dict[str, Any]],
        prompt: str,
        workflow: dict[str, Any],
    ) -> str:
        """
        Run with CrewAI's hierarchical process.
        A manager LLM orchestrates agents and can delegate tasks.
        """
        levels = _topological_levels(tasks_def)

        crewai_agents: dict[str, Agent] = {}
        crewai_tasks: dict[str, Task] = {}

        for level in levels:
            for task_def in level:
                agent_id = task_def.get("agent_id", "")
                agent_def = get_agent(agent_id)
                if not agent_def:
                    raise ValueError(
                        f"Task '{task_def['name']}' references unknown agent '{agent_id}'"
                    )
                if agent_id not in crewai_agents:
                    crewai_agents[agent_id] = _build_crewai_agent(
                        agent_def, self._tool_factory, self._default_llm,
                        allow_delegation_override=True,  # All agents can delegate in hierarchical
                        github_repo_id=task_def.get("github_repo_id", ""),
                    )
                context_tasks = [
                    crewai_tasks[dep_id]
                    for dep_id in task_def.get("depends_on", [])
                    if dep_id in crewai_tasks
                ]
                crewai_tasks[task_def["id"]] = _build_crewai_task(
                    task_def, crewai_agents[agent_id], prompt, context_tasks
                )

        ordered_tasks = [
            crewai_tasks[task_def["id"]]
            for level in levels
            for task_def in level
        ]

        # Resolve manager LLM
        manager_llm_override = workflow.get("manager_llm")
        manager_llm = _resolve_llm(manager_llm_override, self._default_llm)

        crew = Crew(
            agents=list(crewai_agents.values()),
            tasks=ordered_tasks,
            process=Process.hierarchical,
            manager_llm=manager_llm,
            verbose=True,
            memory=False,
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self._kickoff_executor, lambda: crew.kickoff())
        return str(result)
