# AI Hub — Home Assistant Add-on

AI Hub is a **Home Assistant add-on** that brings a dynamic, multi-agent AI orchestration system directly into your smart home. Powered by [CrewAI](https://github.com/crewAIInc/crewAI), it lets you define custom AI agents, build visual multi-step workflows, and run them on demand — all from a built-in web UI accessible via the HA sidebar.

---

## Features

- **Custom Agents** — Define agents with a role, goal, backstory, tool selection, and an optional per-agent LLM override.
- **Visual Workflow Builder** — Build workflows as directed acyclic graphs (DAGs) on a React Flow canvas. Draw dependency edges between tasks to control execution order.
- **Execution Modes** — Choose between *Sequential*, *DAG (parallel branches)*, and *Hierarchical (manager LLM)* execution per workflow.
- **Run on Demand** — Trigger any workflow or individual agent from the UI with a free-text prompt.
- **Real-time Output** — WebSocket-based live status feed shows agent progress as it happens; results are displayed inline.
- **Default Workflows** — Three ready-to-use workflows are seeded on first run: *Code Review*, *HA Automation*, and *HA Assistant*.
- **Built-in Tools** — `ha_sensor_reader` (reads Home Assistant entity states) and `github_commit` (commits files to a GitHub repository).
- **Multiple LLM Providers** — OpenAI, Google Gemini, Anthropic, and OpenRouter are all supported and switchable from the Configuration tab.
- **HA Automation API** — REST endpoints let you trigger workflows and agents from HA automations and scripts.

---

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**.
2. Click the **⋮** menu (top-right) and select **Repositories**.
3. Add the following URL and click **Add**:
   ```
   https://github.com/LovelyPotato-ai/Agent-Hub-HA
   ```
4. Find **AI Hub** in the store and click **Install**.
5. Open the **Configuration** tab and fill in your API keys (see [Configuration](#configuration) below).
6. Click **Start**.
7. Enable **Show in sidebar** to access the AI Hub panel from the HA sidebar.

---

## Configuration

All options are set in the add-on's **Configuration** tab in Home Assistant.

| Option | Description |
|---|---|
| `active_llm_provider` | LLM provider to use: `openai`, `gemini`, `anthropic`, or `openrouter` |
| `active_llm_model` | Model slug for the selected provider (e.g. `gpt-4o`, `gemini-2.0-flash`) |
| `openai_api_key` | OpenAI API key |
| `gemini_api_key` | Google Gemini API key |
| `anthropic_api_key` | Anthropic API key |
| `openrouter_api_key` | OpenRouter API key |
| `github_pat` | GitHub Personal Access Token (required for the `github_commit` tool) |
| `github_repo_owner` | GitHub repository owner/organisation |
| `github_repo_name` | GitHub repository name |
| `github_branch` | Target branch for commits (default: `main`) |
| `log_level` | Logging verbosity: `trace`, `debug`, `info`, `warning`, `error`, or `fatal` |

---

## Usage

The AI Hub UI has four tabs:

### Run
Select a workflow or a single agent from the dropdown, enter a prompt, and click **Run**. The live status feed shows each agent's progress in real time. The final result is displayed below the feed when the job completes.

### Agents
Create, edit, and delete custom agents. Each agent has:
- **Role** — The agent's job title / persona.
- **Goal** — What the agent is trying to achieve.
- **Backstory** — Background context that shapes the agent's behaviour.
- **Tools** — One or more tools the agent can call (`ha_sensor_reader`, `github_commit`).
- **LLM Override** *(optional)* — Use a different provider/model for this specific agent instead of the global default.

### Workflows
Build and manage workflows on a visual canvas:
- **Add tasks** — Each task maps to an agent and carries its own instructions.
- **Draw edges** — Connect tasks to define execution dependencies (DAG).
- **Execution mode** — Set to *Sequential*, *DAG*, or *Hierarchical* per workflow.
- **Run** — Trigger the workflow directly from the canvas with a prompt.

### Settings
View and update the global LLM provider and model without leaving the UI. Full API key management is done in the HA Configuration tab.

---

## API Reference

AI Hub exposes a REST + WebSocket API that can be called from Home Assistant automations, scripts, or external tools.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/run/workflow/{id}` | Run a workflow by ID |
| `POST` | `/api/run/agent/{id}` | Run a single agent by ID |
| `GET` | `/api/agents` | List all agents |
| `GET` | `/api/workflows` | List all workflows |
| `GET` | `/api/tools` | List available tools |
| `GET` | `/api/status` | Current job status |
| `GET` | `/api/result` | Last job result |
| `WS` | `/api/ws?job_id=*` | Real-time status stream for a job |

### Example — trigger a workflow from an HA automation

```yaml
action: rest_command.run_ai_workflow
data:
  workflow_id: "ha_automation"
  prompt: "Create an automation that turns off all lights at midnight."
```

```yaml
rest_command:
  run_ai_workflow:
    url: "http://localhost:7123/api/run/workflow/{{ workflow_id }}"
    method: POST
    content_type: "application/json"
    payload: '{"prompt": "{{ prompt }}"}'
```

---

## Development

### Architecture

| Layer | Technology |
|---|---|
| Add-on runtime | Alpine Linux 3.20, s6-overlay v3 |
| Base image | `ghcr.io/home-assistant/aarch64-base-python:3.12-alpine3.20` |
| Backend | Python 3.12, aiohttp |
| AI engine | CrewAI 1.15.16 |
| Frontend | React 18, Vite, Tailwind CSS, @xyflow/react (React Flow v12) |
| Persistent storage | `/data/agents.json`, `/data/workflows.json` |

### Project layout

```
addon/
├── config.yaml          # HA add-on manifest
├── Dockerfile
├── run.sh               # s6 entrypoint
├── requirements.txt
├── app/
│   ├── server.py        # aiohttp HTTP + WebSocket server
│   ├── orchestrator.py  # job queue and execution controller
│   ├── crew_executor.py # CrewAI integration
│   ├── agent_registry.py
│   ├── workflow_registry.py
│   ├── tool_factory.py
│   ├── llm_factory.py
│   ├── ha_client.py     # Home Assistant REST API client
│   ├── seed_defaults.py # seeds default workflows on first run
│   └── frontend/        # React + Vite source
│       └── src/
│           ├── App.tsx
│           ├── components/
│           └── api/aiHubClient.ts
```

### Building the frontend

```bash
cd addon/app/frontend
npm install
npm run build
```

The built assets are served by the aiohttp backend via HA Ingress.

### Running locally (outside HA)

```bash
pip install -r addon/requirements.txt
python addon/app/server.py
```

Set the required environment variables (`ACTIVE_LLM_PROVIDER`, `OPENAI_API_KEY`, etc.) before starting.

---

## Version

**1.3.1**

---

## License

MIT
