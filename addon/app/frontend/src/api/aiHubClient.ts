/**
 * aiHubClient.ts — AI Hub Add-on REST API wrapper
 * =================================================
 * Typed fetch functions for all AI Hub HTTP endpoints.
 * API root is /api — served by the aiohttp server.
 */

const API_ROOT = '/api'
const WS_ROOT = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api`

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try { const b = await response.json(); message = b.error ?? message } catch { /* ignore */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Status / Result types
// ---------------------------------------------------------------------------

export type HubStatus = 'idle' | 'running' | 'done' | 'error'

export interface StatusResponse { status: HubStatus; active_crew: string }
export interface ResultResponse  { result: string; error: string }

export type WsMessage =
  | { type: 'status'; status: HubStatus; active_crew: string }
  | { type: 'result'; job_id: string; crew: string; status: 'done'; result: string; timestamp: string }
  | { type: 'error';  job_id: string; status: 'error'; message: string; timestamp: string }

export interface RunResponse { job_id: string; status: 'accepted' }

// ---------------------------------------------------------------------------
// Agent types
// ---------------------------------------------------------------------------

export interface AgentDef {
  id: string
  name: string
  role: string
  goal: string
  backstory: string
  tools: string[]
  llm_override: { provider: string; model: string } | null
  allow_delegation: boolean
  max_iter: number
  created_at: string
  updated_at: string
}

export type AgentCreate = Omit<AgentDef, 'id' | 'created_at' | 'updated_at'>
export type AgentUpdate = Partial<AgentCreate>

// ---------------------------------------------------------------------------
// Workflow / Task types
// ---------------------------------------------------------------------------

export interface TaskDef {
  id: string
  name: string
  description: string
  agent_id: string
  expected_output: string
  depends_on: string[]
  allow_delegation: boolean
  position: { x: number; y: number }
}

export type TaskCreate = Omit<TaskDef, 'id'> & { id?: string }

export interface WorkflowDef {
  id: string
  name: string
  description: string
  process: 'sequential' | 'hierarchical' | 'dag'
  manager_llm: { provider: string; model: string } | null
  tasks: TaskDef[]
  created_at: string
  updated_at: string
}

export type WorkflowCreate = Omit<WorkflowDef, 'id' | 'created_at' | 'updated_at'>
export type WorkflowUpdate = Partial<WorkflowCreate>

// ---------------------------------------------------------------------------
// Tool types
// ---------------------------------------------------------------------------

export interface ToolDef { id: string; name: string; description: string }

// ---------------------------------------------------------------------------
// Settings types
// ---------------------------------------------------------------------------

export interface AgentOverride { provider: string; model: string }

export interface SettingsPayload {
  active_llm_provider: string
  active_llm_model: string
  github_branch: string
  github_repo_owner: string
  github_repo_name: string
  agent_overrides: Record<string, AgentOverride>
  openai_api_key?: string
  gemini_api_key?: string
  anthropic_api_key?: string
  openrouter_api_key?: string
  github_pat?: string
}

export interface SettingsResponse extends SettingsPayload {
  keys_configured: Record<string, boolean>
}

export interface SettingsMetadata {
  agent_roles: Record<string, string>
  provider_models: Record<string, string[]>
}

export interface SaveSettingsResponse { status: 'ok' | 'error'; message: string }

// ---------------------------------------------------------------------------
// Agent API
// ---------------------------------------------------------------------------

export const listAgents    = ()                          => apiFetch<AgentDef[]>('/agents')
export const getAgent      = (id: string)                => apiFetch<AgentDef>(`/agents/${id}`)
export const createAgent   = (data: AgentCreate)         => apiFetch<AgentDef>('/agents', { method: 'POST', body: JSON.stringify(data) })
export const updateAgent   = (id: string, data: AgentUpdate) => apiFetch<AgentDef>(`/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteAgent   = (id: string)                => apiFetch<{ status: string }>(`/agents/${id}`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Workflow API
// ---------------------------------------------------------------------------

export const listWorkflows   = ()                              => apiFetch<WorkflowDef[]>('/workflows')
export const getWorkflow     = (id: string)                    => apiFetch<WorkflowDef>(`/workflows/${id}`)
export const createWorkflow  = (data: WorkflowCreate)          => apiFetch<WorkflowDef>('/workflows', { method: 'POST', body: JSON.stringify(data) })
export const updateWorkflow  = (id: string, data: WorkflowUpdate) => apiFetch<WorkflowDef>(`/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteWorkflow  = (id: string)                    => apiFetch<{ status: string }>(`/workflows/${id}`, { method: 'DELETE' })

// ---------------------------------------------------------------------------
// Tools API
// ---------------------------------------------------------------------------

export const listTools = () => apiFetch<ToolDef[]>('/tools')

// ---------------------------------------------------------------------------
// Run API
// ---------------------------------------------------------------------------

export const runWorkflow = (id: string, prompt: string) =>
  apiFetch<RunResponse>(`/run/workflow/${id}`, { method: 'POST', body: JSON.stringify({ prompt }) })

export const runAgent = (id: string, prompt: string) =>
  apiFetch<RunResponse>(`/run/agent/${id}`, { method: 'POST', body: JSON.stringify({ prompt }) })

// ---------------------------------------------------------------------------
// Status / Result
// ---------------------------------------------------------------------------

export const getStatus = () => apiFetch<StatusResponse>('/status')
export const getResult = () => apiFetch<ResultResponse>('/result')

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export const getSettings         = ()                              => apiFetch<SettingsResponse>('/settings')
export const saveSettings        = (p: Partial<SettingsPayload>)   => apiFetch<SaveSettingsResponse>('/settings/save', { method: 'POST', body: JSON.stringify(p) })
export const getSettingsMetadata = ()                              => apiFetch<SettingsMetadata>('/settings/metadata')

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------

export function createWebSocket(jobId: string = '*'): WebSocket {
  return new WebSocket(`${WS_ROOT}/ws?job_id=${encodeURIComponent(jobId)}`)
}
