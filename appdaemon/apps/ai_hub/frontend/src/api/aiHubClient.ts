/**
 * aiHubClient.ts — AppDaemon REST API wrapper
 * =============================================
 * Provides typed fetch functions for all AI Hub HTTP endpoints.
 *
 * Base URL is read from the Vite env variable VITE_API_BASE_URL.
 * During development (npm run dev), the Vite proxy in vite.config.ts
 * forwards /api/appdaemon/* to http://homeassistant.local:5050.
 * In production (served from AppDaemon), the base URL is empty (same origin).
 *
 * Authentication: AppDaemon API password sent as Bearer token.
 * Set VITE_AD_PASSWORD in a .env.local file during development.
 * In production the password is injected at build time or left empty
 * if AppDaemon is configured without a password on the local network.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const AD_PASSWORD = import.meta.env.VITE_AD_PASSWORD ?? ''

const API_ROOT = `${BASE}/api/appdaemon/ai_hub`
const WS_ROOT = BASE
  ? BASE.replace(/^http/, 'ws') + '/api/appdaemon/ai_hub'
  : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/appdaemon/ai_hub`

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CrewId = 'code_review' | 'ha_automation' | 'ha_assistant'

export type HubStatus = 'idle' | 'running' | 'done' | 'error'

export interface TriggerPayload {
  crew: CrewId
  prompt: string
  options?: Record<string, unknown>
}

export interface TriggerResponse {
  job_id: string
  status: 'accepted'
}

export interface StatusResponse {
  status: HubStatus
  active_crew: string
}

export interface ResultResponse {
  result: string
  error: string
}

export type WsMessage =
  | { type: 'status'; status: HubStatus; active_crew: string }
  | { type: 'result'; job_id: string; crew: string; status: 'done'; result: string; timestamp: string }
  | { type: 'error'; job_id: string; status: 'error'; message: string; timestamp: string }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (AD_PASSWORD) {
    headers['Authorization'] = `Bearer ${AD_PASSWORD}`
  }
  return headers
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const body = await response.json()
      message = body.error ?? message
    } catch {
      // ignore JSON parse error
    }
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * POST /trigger — start a crew run
 * Returns a job_id that can be used to subscribe to WebSocket updates.
 */
export async function triggerCrew(payload: TriggerPayload): Promise<TriggerResponse> {
  return apiFetch<TriggerResponse>('/trigger', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * GET /status — current hub status and active crew name
 */
export async function getStatus(): Promise<StatusResponse> {
  return apiFetch<StatusResponse>('/status')
}

/**
 * GET /result — last result and error strings
 */
export async function getResult(): Promise<ResultResponse> {
  return apiFetch<ResultResponse>('/result')
}

// ---------------------------------------------------------------------------
// Settings API
// ---------------------------------------------------------------------------

export interface AgentOverride {
  provider: string
  model: string
}

export interface SettingsPayload {
  active_llm_provider: string
  active_llm_model: string
  github_branch: string
  github_repo_owner: string
  github_repo_name: string
  agent_overrides: Record<string, AgentOverride>
  // Write-only fields — send to save, never returned from GET
  openai_api_key?: string
  gemini_api_key?: string
  anthropic_api_key?: string
  openrouter_api_key?: string
  github_pat?: string
  appdaemon_token?: string
}

export interface SettingsResponse extends SettingsPayload {
  keys_configured: Record<string, boolean>
}

export interface SettingsMetadata {
  agent_roles: Record<string, string>
  provider_models: Record<string, string[]>
}

export interface SaveSettingsResponse {
  status: 'ok' | 'error'
  message: string
}

/**
 * GET /settings — load current settings (keys replaced with boolean flags)
 */
export async function getSettings(): Promise<SettingsResponse> {
  return apiFetch<SettingsResponse>('/settings')
}

/**
 * POST /settings/save — persist settings to apps.yaml and secrets.yaml
 */
export async function saveSettings(payload: Partial<SettingsPayload>): Promise<SaveSettingsResponse> {
  return apiFetch<SaveSettingsResponse>('/settings/save', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * GET /settings/metadata — agent roles + provider→model lists for dropdowns
 */
export async function getSettingsMetadata(): Promise<SettingsMetadata> {
  return apiFetch<SettingsMetadata>('/settings/metadata')
}

/**
 * Create a WebSocket connection to /ws?job_id=<id>
 * Use job_id='*' to subscribe to all jobs.
 *
 * Returns the WebSocket instance. The caller is responsible for
 * attaching onmessage / onerror / onclose handlers and calling ws.close().
 */
export function createWebSocket(jobId: string = '*'): WebSocket {
  const token = AD_PASSWORD ? `?token=${encodeURIComponent(AD_PASSWORD)}&job_id=${encodeURIComponent(jobId)}` : `?job_id=${encodeURIComponent(jobId)}`
  return new WebSocket(`${WS_ROOT}/ws${token}`)
}
