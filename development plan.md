# Project Specification: Multi-Agent AI Hub on Home Assistant OS

## 1. Project Overview & Objective
The goal is to build a lightweight, custom multi-agent AI orchestrator running locally on a Home Assistant (HA) Green device. The system will use **CrewAI** for agent orchestration, running inside the **AppDaemon** HA Add-on environment. Heavy AI inference will be offloaded to Cloud LLM APIs to respect the local hardware constraints.

## 2. Hardware & Environment Constraints
**Host Device:** Home Assistant Green (HAOS)
*   **CPU:** Rockchip RK3566 quad-core (Current average load: ~3%)
*   **RAM:** 4 GB (Current usage: 2.6 GB / 4.0 GB)
*   **OS Level Constraint:** HAOS is a locked-down appliance OS. We cannot use native `docker run` or install system-level packages. 
*   **Execution Sandbox:** We will use the official **AppDaemon** Add-on as our Python execution environment.

## 3. Technology Stack
*   **Orchestration Framework:** CrewAI (Python)
*   **Host Environment:** AppDaemon (Python 3.x) inside HAOS
*   **LLM Provider:** Cloud APIs (OpenAI, Gemini, or Anthropic via LangChain wrappers). *Strict rule: NO local GGUF/LLM loading in this container.*
*   **Future UI (Phase 4):** A custom dashboard built with React, Vite, and Tailwind CSS (deployed via HA Ingress or external hosting).

---

## 4. Implementation Plan & Phases

### Phase 1: AppDaemon Environment Configuration
**Goal:** Set up the isolated Python environment for CrewAI.
**Action Items for AI:**
1.  Provide the exact `appdaemon.yaml` configuration required to inject CrewAI.
2.  Specify the `python_packages` array (e.g., `crewai`, `langchain-openai`, `github3.py`).
3.  Define the exact folder structure within `/config/appdaemon/apps/ai_hub/`.
4.  Provide instructions on how to securely pass LLM API keys and GitHub PAT tokens from HA `secrets.yaml` to the AppDaemon app.

### Phase 2: The AppDaemon Base Class Integration
**Goal:** Bridge CrewAI with Home Assistant's event bus.
**Action Items for AI:**
1.  Write a Python class `AIHubOrchestrator` that inherits from `hass.Hass`.
2.  Implement an `initialize()` function that listens to a specific HA entity (e.g., `input_button.trigger_ai_hub` or an HA Event) to start the CrewAI process.
3.  Implement a logging/notification mechanism so the agent's progress and final output are sent back to HA (e.g., via `self.call_service("notify/notify", message=...)` or updating an `input_text` entity).

### Phase 3: CrewAI Multi-Agent Architecture
**Goal:** Build a sample multi-agent workflow (e.g., a "DevOps/Coding" crew).
**Action Items for AI:**
1.  **Define Agents:** Create at least two agents.
    *   *Developer Agent:* Writes code based on user requests.
    *   *DevOps/Reviewer Agent:* Reviews the code and prepares it for deployment.
2.  **Define Tasks:** Create sequential tasks that pass outputs between these agents.
3.  **Define Custom Tools:**
    *   Write a custom Python Tool that allows the DevOps Agent to interact with the GitHub API (commit and push code to a specified repository).
    *   Write a custom Python Tool that allows agents to read the current state of a Home Assistant sensor (e.g., reading a Zigbee switch state via the AppDaemon API).

### Phase 4: Frontend Hub Concept (React/Vite/Tailwind)
**Goal:** Provide the architectural blueprint for a future visual UI.
**Action Items for AI:**
1.  Outline how a Vite + React + Tailwind CSS frontend can communicate with this AppDaemon backend.
2.  Design a REST/Webhook workflow: How can the React app send a payload to HA (via Long-Lived Access Tokens and Webhooks), which then triggers the AppDaemon script, and how does the React app receive the asynchronous result?

---

## 5. Development Guidelines for Antigravity AI
*   **Modularity:** Write the CrewAI logic in separate `.py` modules (e.g., `agents.py`, `tasks.py`, `tools.py`) and import them into the main AppDaemon app file. Do not put a 500-line monolithic script in `main.py`.
*   **Asynchronous Execution:** Ensure that the CrewAI `kickoff()` method, which is blocking and network-heavy, does not freeze the AppDaemon main event loop. Use `self.run_in_executor` or AppDaemon's thread management appropriately.
*   **Error Handling:** Cloud API timeouts and GitHub API rate limits must be caught gracefully. The system should report errors back to Home Assistant rather than just crashing silently in the logs.

**Please start by providing the code and configurations for Phase 1 and Phase 2.**