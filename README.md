# AI Hub — Multi-Agent Orchestrator for Home Assistant

A lightweight, modular multi-agent AI system running locally on a **Home Assistant Green** device. Uses **CrewAI** for agent orchestration inside the **AppDaemon** add-on. All LLM inference is offloaded to cloud APIs — no local model loading.

---

## Architecture

```
AppDaemon Add-on (Python)
├── main.py              ← AIHubOrchestrator (hass.Hass subclass)
├── llm_factory.py       ← Configurable LLM provider (OpenAI / Gemini / Anthropic / OpenRouter)
├── crew_router.py       ← Runtime crew selector
├── agents.py            ← All CrewAI Agent definitions
├── tasks.py             ← All CrewAI Task definitions
├── tools.py             ← GitHubCommitTool + HASensorReaderTool
└── crews/
    ├── code_review_crew.py    ← Developer → Reviewer → DevOps
    ├── ha_automation_crew.py  ← NL prompt → HA YAML → GitHub
    └── ha_assistant_crew.py   ← Survey sensors → suggest → commit

React Frontend (Vite + Tailwind)
└── frontend/src/
    ├── App.tsx
    ├── api/aiHubClient.ts
    ├── hooks/useCrewStatus.ts
    └── components/
        ├── CrewSelector.tsx
        ├── PromptInput.tsx
        ├── StatusBadge.tsx
        ├── StatusFeed.tsx
        └── ResultPanel.tsx
```

---

## Prerequisites

- Home Assistant OS running on HA Green (or any HAOS device)
- AppDaemon add-on installed from the HA Add-on Store
- At least one LLM API key (OpenAI, Gemini, Anthropic, or OpenRouter)
- A GitHub Personal Access Token with `Contents: read & write` permission
- Node.js 20+ (for building the frontend — can be done on your dev machine)

---

## Phase 1 — AppDaemon Setup

### Step 1: Copy secrets

Add the entries from [`ha_config/secrets.yaml.template`](ha_config/secrets.yaml.template) to your `/config/secrets.yaml` on the HA device. Fill in your real API keys.

```yaml
# Minimum required entries:
appdaemon_token: "YOUR_HA_LONG_LIVED_ACCESS_TOKEN"
appdaemon_api_password: "CHOOSE_A_STRONG_PASSWORD"
active_llm_provider: "openai"          # or gemini | anthropic | openrouter
active_llm_model: "gpt-4o"
openai_api_key: "sk-..."
github_pat: "ghp_..."
github_repo_owner: "your-username"
github_repo_name: "your-repo"
```

### Step 2: Copy AppDaemon config

Copy [`appdaemon/appdaemon.yaml`](appdaemon/appdaemon.yaml) to `/config/appdaemon/appdaemon.yaml`.

> **Important:** Update `time_zone`, `latitude`, `longitude`, and `elevation` to match your location.

### Step 3: Copy the app files

Copy the entire [`appdaemon/apps/ai_hub/`](appdaemon/apps/ai_hub/) directory to `/config/appdaemon/apps/ai_hub/` on your HA device.

Using the HA File Editor add-on or SSH:

```bash
# Via SSH (replace with your HA IP)
scp -r appdaemon/apps/ai_hub/ root@homeassistant.local:/config/appdaemon/apps/
```

### Step 4: Add HA helper entities

Add the contents of [`ha_config/ai_hub_entities.yaml`](ha_config/ai_hub_entities.yaml) to your `/config/configuration.yaml`:

```yaml
# In /config/configuration.yaml:
input_text: !include ai_hub_entities.yaml
input_button: !include ai_hub_entities.yaml
```

Or copy the `input_text:` and `input_button:` sections directly into `configuration.yaml`.

### Step 5: Add HA automations

Add the contents of [`ha_config/automations.yaml`](ha_config/automations.yaml) to your HA automations (via the UI or file).

### Step 6: Add HA Ingress panel

Add to `/config/configuration.yaml`:

```yaml
panel_iframe:
  ai_hub:
    title: "AI Hub"
    icon: mdi:robot
    url: "http://homeassistant.local:5050/api/appdaemon/ai_hub/"
    require_admin: true
```

### Step 7: Restart

1. Restart Home Assistant (Developer Tools → Restart)
2. Restart the AppDaemon add-on

Check the AppDaemon logs for:
```
AI Hub Orchestrator ready.
Listening for HA event: 'ai_hub_trigger'
HTTP endpoints registered at /api/appdaemon/ai_hub/
```

---

## Phase 4 — Build the Frontend

The frontend is a Vite + React + Tailwind app. Build it on your development machine, then copy the `dist/` output to the HA device.

```bash
cd appdaemon/apps/ai_hub/frontend

# Install dependencies
npm install

# Development server (proxies API calls to HA Green)
npm run dev

# Production build
npm run build

# Copy dist/ to HA device
scp -r dist/ root@homeassistant.local:/config/appdaemon/apps/ai_hub/frontend/
```

The frontend will be accessible at:
- Via HA Ingress panel: **AI Hub** in the HA sidebar
- Directly: `http://homeassistant.local:5050/api/appdaemon/ai_hub/`

### Development environment variables

Create `appdaemon/apps/ai_hub/frontend/.env.local` for local development:

```env
VITE_API_BASE_URL=http://homeassistant.local:5050
VITE_AD_PASSWORD=your_appdaemon_api_password
```

---

## Triggering Crews

### Via HA Dashboard (buttons)

Use the `input_button` entities added in Step 4. The automations in `ha_config/automations.yaml` wire them to the trigger event.

### Via HA Developer Tools

Go to **Developer Tools → Events** and fire:

```yaml
Event type: ai_hub_trigger
Event data:
  crew: code_review
  prompt: "Write a Python function that validates HA entity IDs"
  options: {}
```

Valid `crew` values: `code_review` | `ha_automation` | `ha_assistant`

### Via the React Frontend

Select a crew, enter a prompt, and click **Run Crew**.

### Via REST API

```bash
curl -X POST http://homeassistant.local:5050/api/appdaemon/ai_hub/trigger \
  -H "Authorization: Bearer YOUR_AD_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{"crew": "code_review", "prompt": "Write a YAML parser utility"}'
```

---

## Switching LLM Providers

Edit `/config/secrets.yaml` on the HA device:

```yaml
active_llm_provider: "gemini"          # openai | gemini | anthropic | openrouter
active_llm_model: "gemini-2.5-pro"
gemini_api_key: "AIza..."
```

Restart the AppDaemon add-on to apply. No Python code changes needed.

---

## Available Crews

| Crew | Trigger value | Description |
|---|---|---|
| Code Review | `code_review` | Developer writes code → Reviewer critiques → DevOps commits to GitHub |
| HA Automation | `ha_automation` | NL prompt → HA automation YAML → GitHub commit |
| HA Assistant | `ha_assistant` | Survey HA sensors → suggest automations → commit top pick |

### HA Automation crew options

```json
{
  "crew": "ha_automation",
  "prompt": "Turn off all lights when everyone leaves home",
  "options": {
    "entities_to_read": ["person.john", "light.living_room"]
  }
}
```

### HA Assistant crew options

```json
{
  "crew": "ha_assistant",
  "prompt": "Suggest energy-saving automations",
  "options": {
    "entities_to_survey": [
      "sensor.living_room_temperature",
      "switch.living_room_ac",
      "binary_sensor.motion_living_room"
    ]
  }
}
```

---

## REST API Reference

All endpoints are at `http://homeassistant.local:5050/api/appdaemon/ai_hub/`

| Endpoint | Method | Description |
|---|---|---|
| `/trigger` | POST | Start a crew run |
| `/status` | GET | Current status and active crew |
| `/result` | GET | Last result and error |
| `/ws?job_id=*` | WebSocket | Real-time status/result push |

---

## File Structure

```
Agent Hub HA/
├── README.md
├── development plan.md
├── plans/
│   └── architecture.md          ← Full architecture specification
├── appdaemon/
│   ├── appdaemon.yaml           ← Deploy to /config/appdaemon/appdaemon.yaml
│   └── apps/
│       └── ai_hub/
│           ├── apps.yaml        ← Deploy to /config/appdaemon/apps/ai_hub/apps.yaml
│           ├── main.py          ← AIHubOrchestrator
│           ├── llm_factory.py   ← LLM provider factory
│           ├── crew_router.py   ← Runtime crew selector
│           ├── agents.py        ← Agent definitions
│           ├── tasks.py         ← Task definitions
│           ├── tools.py         ← GitHubCommitTool + HASensorReaderTool
│           ├── crews/
│           │   ├── __init__.py
│           │   ├── code_review_crew.py
│           │   ├── ha_automation_crew.py
│           │   └── ha_assistant_crew.py
│           └── frontend/        ← React/Vite/Tailwind frontend
│               ├── package.json
│               ├── vite.config.ts
│               ├── tailwind.config.ts
│               ├── index.html
│               └── src/
│                   ├── main.tsx
│                   ├── App.tsx
│                   ├── api/aiHubClient.ts
│                   ├── hooks/useCrewStatus.ts
│                   └── components/
│                       ├── CrewSelector.tsx
│                       ├── PromptInput.tsx
│                       ├── StatusBadge.tsx
│                       ├── StatusFeed.tsx
│                       └── ResultPanel.tsx
└── ha_config/
    ├── secrets.yaml.template    ← Copy entries to /config/secrets.yaml
    ├── ai_hub_entities.yaml     ← HA helper entities
    └── automations.yaml         ← HA automations for button triggers
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `LLM factory error: API key missing` | Placeholder key in secrets.yaml | Set real API key for `active_llm_provider` |
| `Unknown crew: 'xyz'` | Invalid crew name in trigger | Use `code_review`, `ha_automation`, or `ha_assistant` |
| `GitHub authentication failed` | Invalid PAT | Regenerate PAT with `Contents: read & write` scope |
| `Entity 'xyz' not found` | Wrong entity ID | Check entity ID in HA Developer Tools → States |
| Frontend shows blank page | `dist/` not copied | Run `npm run build` and copy `dist/` to HA device |
| AppDaemon won't start | Missing python package | Check AppDaemon add-on logs; verify `python_packages` in `appdaemon.yaml` |
