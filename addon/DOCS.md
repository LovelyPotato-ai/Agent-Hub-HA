# AI Hub — Add-on Documentation

A multi-agent AI orchestrator powered by **CrewAI**, running as a native Home Assistant add-on. Supports OpenAI, Google Gemini, Anthropic Claude, and OpenRouter. Includes a React dashboard served via HA Ingress.

---

## Installation

1. In HA: **Settings → Add-ons → Add-on Store → ⋮ (three dots) → Repositories**
2. Add your GitHub repository URL
3. Find **AI Hub** in the store → **Install**
4. Go to the **Configuration** tab and fill in your API keys
5. Click **Start**
6. Open the **AI Hub** panel in the HA sidebar

---

## Configuration

All settings are configured in the add-on's **Configuration** tab. No file editing required.

| Option | Description | Example |
|---|---|---|
| `active_llm_provider` | LLM provider to use | `openai` |
| `active_llm_model` | Model slug for the provider | `gpt-4o` |
| `openai_api_key` | OpenAI API key | `sk-...` |
| `gemini_api_key` | Google Gemini API key | `AIza...` |
| `anthropic_api_key` | Anthropic Claude API key | `sk-ant-...` |
| `openrouter_api_key` | OpenRouter API key | `sk-or-...` |
| `github_pat` | GitHub Personal Access Token | `ghp_...` |
| `github_repo_owner` | GitHub username or org | `your-username` |
| `github_repo_name` | Target repository name | `your-repo` |
| `github_branch` | Branch to commit to | `main` |
| `log_level` | Logging verbosity | `info` |

You only need to fill in the API key for your chosen `active_llm_provider`. The others can be left empty.

---

## Available Crews

Trigger a crew by firing the `ai_hub_trigger` HA event with a payload:

```yaml
event_type: ai_hub_trigger
event_data:
  crew: code_review        # or: ha_automation | ha_assistant
  prompt: "Write a Python function that validates HA entity IDs"
  options: {}
```

### `code_review`
**Developer → Reviewer → DevOps**

Writes code from your prompt, reviews it for quality and security, then commits the approved version to GitHub.

```yaml
event_data:
  crew: code_review
  prompt: "Write a Python utility that parses Home Assistant entity IDs"
```

### `ha_automation`
**NL prompt → HA automation YAML → GitHub commit**

Generates a valid Home Assistant automation YAML from a natural language description, optionally reading current entity states for context.

```yaml
event_data:
  crew: ha_automation
  prompt: "Turn off all lights when everyone leaves home"
  options:
    entities_to_read:
      - person.john
      - light.living_room
```

### `ha_assistant`
**Survey sensors → suggest automations → commit top pick**

Reads multiple HA sensor states, analyses patterns, suggests practical automations, and commits the highest-impact suggestion to GitHub.

```yaml
event_data:
  crew: ha_assistant
  prompt: "Suggest energy-saving automations for the living room"
  options:
    entities_to_survey:
      - sensor.living_room_temperature
      - switch.living_room_ac
      - binary_sensor.motion_living_room
```

---

## HA Helper Entities

The add-on writes results to these HA entities (create them in your `configuration.yaml`):

```yaml
input_text:
  ai_hub_status:
    name: "AI Hub Status"
    initial: "idle"
    max: 50
  ai_hub_result:
    name: "AI Hub Result"
    initial: ""
    max: 255
  ai_hub_active_crew:
    name: "AI Hub Active Crew"
    initial: ""
    max: 50
  ai_hub_error:
    name: "AI Hub Last Error"
    initial: ""
    max: 255
```

---

## REST API

The add-on exposes a REST API at `http://YOUR_HA_IP:8099/api/`:

| Endpoint | Method | Description |
|---|---|---|
| `/api/trigger` | POST | Start a crew run |
| `/api/status` | GET | Current status and active crew |
| `/api/result` | GET | Last result and error |
| `/api/ws?job_id=*` | WebSocket | Real-time status/result push |
| `/api/settings` | GET | Current settings (keys masked) |
| `/api/settings/save` | POST | Save settings |
| `/api/settings/metadata` | GET | Provider/model lists for UI |
| `/api/health` | GET | Health check |

---

## Switching LLM Providers

Change `active_llm_provider` and `active_llm_model` in the Configuration tab, then restart the add-on. No code changes needed.

Supported providers:
- `openai` — GPT-4o, GPT-4.1, GPT-4o-mini, o1, o3-mini
- `gemini` — Gemini 2.5 Pro, Gemini 2.0 Flash
- `anthropic` — Claude Sonnet 4.5, Claude Opus 4
- `openrouter` — Any model from openrouter.ai/models

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `LLM factory error: API key missing` | Empty or placeholder key | Fill in the key for your active provider in Configuration |
| `Unknown crew: 'xyz'` | Invalid crew name | Use `code_review`, `ha_automation`, or `ha_assistant` |
| `GitHub authentication failed` | Invalid PAT | Regenerate PAT with Contents: read & write scope |
| `Entity 'xyz' not found` | Wrong entity ID | Check entity ID in HA Developer Tools → States |
| Add-on won't start | Build failure | Check the add-on Log tab for the specific error |
