/**
 * SettingsPanel.tsx — Runtime settings editor
 * =============================================
 * Allows editing:
 *   - Global LLM provider + model
 *   - Per-agent provider + model overrides
 *   - API keys (write-only — displayed as masked dots if already set)
 *   - GitHub config (repo owner, repo name, branch, PAT)
 *
 * On save, calls POST /api/settings/save.
 * Settings are persisted by the addon server.
 */

import { useCallback, useEffect, useState, type FC } from 'react'
import {
  getSettings,
  getSettingsMetadata,
  saveSettings,
  type AgentOverride,
  type SettingsMetadata,
  type SettingsResponse,
} from '../api/aiHubClient'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface KeyField {
  key: string
  label: string
  placeholder: string
  provider?: string // if set, only show when this provider is active
}

const KEY_FIELDS: KeyField[] = [
  { key: 'openai_api_key',     label: 'OpenAI API Key',     placeholder: 'sk-...',        provider: 'openai' },
  { key: 'gemini_api_key',     label: 'Gemini API Key',     placeholder: 'AIza...',       provider: 'gemini' },
  { key: 'anthropic_api_key',  label: 'Anthropic API Key',  placeholder: 'sk-ant-...',    provider: 'anthropic' },
  { key: 'openrouter_api_key', label: 'OpenRouter API Key', placeholder: 'sk-or-...',     provider: 'openrouter' },
  { key: 'github_pat',         label: 'GitHub PAT',         placeholder: 'ghp_...' },
]

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface SectionProps { title: string; children: React.ReactNode }
const Section: FC<SectionProps> = ({ title, children }) => (
  <div className="card flex flex-col gap-4">
    <h3 className="text-sm font-semibold text-ha-muted uppercase tracking-wider">{title}</h3>
    {children}
  </div>
)

interface FieldProps { label: React.ReactNode; hint?: string; children: React.ReactNode }
const Field: FC<FieldProps> = ({ label, hint, children }) => (
  <div className="flex flex-col gap-1.5">
    <label className="text-sm font-medium text-ha-text">{label}</label>
    {children}
    {hint && <p className="text-xs text-ha-muted">{hint}</p>}
  </div>
)

interface SelectProps {
  value: string
  onChange: (v: string) => void
  options: string[]
  disabled?: boolean
  allowCustom?: boolean
}
const Select: FC<SelectProps> = ({ value, onChange, options, disabled, allowCustom }) => {
  const isCustom = allowCustom && !options.includes(value) && value !== ''
  return (
    <div className="flex gap-2">
      <select
        value={isCustom ? '__custom__' : value}
        onChange={e => {
          if (e.target.value === '__custom__') onChange('')
          else onChange(e.target.value)
        }}
        disabled={disabled}
        className="flex-1 rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue disabled:opacity-50"
      >
        {options.map(o => <option key={o} value={o}>{o}</option>)}
        {allowCustom && <option value="__custom__">Custom…</option>}
      </select>
      {(allowCustom && (isCustom || value === '')) && (
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="e.g. openai/gpt-4o"
          disabled={disabled}
          className="flex-1 rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue disabled:opacity-50"
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const SettingsPanel: FC = () => {
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [metadata, setMetadata] = useState<SettingsMetadata | null>(null)
  const [keyValues, setKeyValues] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState<{ status: 'ok' | 'error'; message: string } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [s, m] = await Promise.all([getSettings(), getSettingsMetadata()])
      setSettings(s)
      setMetadata(m)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load settings')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  function updateSetting<K extends keyof SettingsResponse>(key: K, value: SettingsResponse[K]) {
    setSettings(prev => prev ? { ...prev, [key]: value } : prev)
  }

  function updateAgentOverride(agent: string, field: keyof AgentOverride, value: string) {
    setSettings(prev => {
      if (!prev) return prev
      return {
        ...prev,
        agent_overrides: {
          ...prev.agent_overrides,
          [agent]: { ...prev.agent_overrides[agent], [field]: value },
        },
      }
    })
  }

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    setSaveResult(null)
    try {
      const payload = {
        active_llm_provider: settings.active_llm_provider,
        active_llm_model: settings.active_llm_model,
        github_branch: settings.github_branch,
        github_repo_owner: settings.github_repo_owner,
        github_repo_name: settings.github_repo_name,
        agent_overrides: settings.agent_overrides,
        ...keyValues,
      }
      const result = await saveSettings(payload)
      setSaveResult(result)
      if (result.status === 'ok') {
        setKeyValues({}) // clear key fields after successful save
        await load()     // reload to get updated key_configured flags
      }
    } catch (err) {
      setSaveResult({ status: 'error', message: err instanceof Error ? err.message : 'Save failed' })
    } finally {
      setSaving(false)
    }
  }

  // ── Loading / error states ─────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-ha-muted gap-3">
        <svg className="w-5 h-5 animate-spin text-ha-blue" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        Loading settings…
      </div>
    )
  }

  if (loadError || !settings || !metadata) {
    return (
      <div className="rounded-lg border border-red-800 bg-red-900/20 p-4 text-red-300 text-sm">
        {loadError ?? 'Failed to load settings'}
        <button onClick={load} className="ml-3 underline text-red-400 hover:text-red-300">Retry</button>
      </div>
    )
  }

  const activeProvider = settings.active_llm_provider
  const activeModels = metadata.provider_models[activeProvider] ?? []

  return (
    <div className="flex flex-col gap-5">

      {/* ── Save result banner ──────────────────────────────────────── */}
      {saveResult && (
        <div className={`rounded-lg border px-4 py-3 text-sm flex items-start gap-2 ${
          saveResult.status === 'ok'
            ? 'border-green-700 bg-green-900/20 text-green-300'
            : 'border-red-700 bg-red-900/20 text-red-300'
        }`}>
          <span>{saveResult.status === 'ok' ? '✅' : '⚠'}</span>
          <span>{saveResult.message}</span>
        </div>
      )}

      {/* ── Global LLM ─────────────────────────────────────────────── */}
      <Section title="Global LLM Provider">
        <Field label="Provider" hint="All agents use this provider unless overridden below.">
          <Select
            value={activeProvider}
            onChange={v => { updateSetting('active_llm_provider', v); updateSetting('active_llm_model', '') }}
            options={Object.keys(metadata.provider_models)}
          />
        </Field>
        <Field label="Model">
          <Select
            value={settings.active_llm_model}
            onChange={v => updateSetting('active_llm_model', v)}
            options={activeModels}
            allowCustom={activeProvider === 'openrouter'}
          />
        </Field>
      </Section>

      {/* ── Per-agent overrides ─────────────────────────────────────── */}
      <Section title="Per-Agent Model Overrides">
        <p className="text-xs text-ha-muted -mt-2">
          Leave provider empty to use the global setting above.
        </p>
        {Object.entries(metadata.agent_roles).map(([agentKey, roleLabel]) => {
          const override = settings.agent_overrides[agentKey] ?? { provider: '', model: '' }
          const overrideModels = override.provider ? (metadata.provider_models[override.provider] ?? []) : []
          return (
            <div key={agentKey} className="rounded-lg border border-ha-border bg-ha-bg p-3 flex flex-col gap-2">
              <p className="text-xs font-semibold text-ha-text">{roleLabel}</p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-xs text-ha-muted mb-1">Provider</p>
                  <Select
                    value={override.provider}
                    onChange={v => { updateAgentOverride(agentKey, 'provider', v); updateAgentOverride(agentKey, 'model', '') }}
                    options={['', ...Object.keys(metadata.provider_models)]}
                  />
                </div>
                <div>
                  <p className="text-xs text-ha-muted mb-1">Model</p>
                  <Select
                    value={override.model}
                    onChange={v => updateAgentOverride(agentKey, 'model', v)}
                    options={['', ...overrideModels]}
                    disabled={!override.provider}
                    allowCustom={override.provider === 'openrouter'}
                  />
                </div>
              </div>
            </div>
          )
        })}
      </Section>

      {/* ── GitHub config ───────────────────────────────────────────── */}
      <Section title="GitHub Configuration">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Repo Owner">
            <input
              type="text"
              value={settings.github_repo_owner}
              onChange={e => updateSetting('github_repo_owner', e.target.value)}
              placeholder="your-username"
              className="rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue"
            />
          </Field>
          <Field label="Repo Name">
            <input
              type="text"
              value={settings.github_repo_name}
              onChange={e => updateSetting('github_repo_name', e.target.value)}
              placeholder="your-repo"
              className="rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue"
            />
          </Field>
        </div>
        <Field label="Branch">
          <input
            type="text"
            value={settings.github_branch}
            onChange={e => updateSetting('github_branch', e.target.value)}
            placeholder="main"
            className="w-40 rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue"
          />
        </Field>
      </Section>

      {/* ── API Keys ────────────────────────────────────────────────── */}
      <Section title="API Keys">
        <p className="text-xs text-ha-muted -mt-2">
          Keys are stored securely by the add-on.
          Leave a field blank to keep the existing value. A green dot means the key is already configured.
        </p>
        <div className="flex flex-col gap-3">
          {KEY_FIELDS.map(field => {
            const isConfigured = settings.keys_configured[
              field.provider ?? field.key.replace('_api_key', '').replace('github_pat', 'github_pat')
            ] ?? false
            const currentValue = keyValues[field.key] ?? ''
            return (
              <Field
                key={field.key}
                label={
                  <span className="flex items-center gap-2">
                    {field.label}
                    <span className={`w-2 h-2 rounded-full inline-block ${isConfigured ? 'bg-green-400' : 'bg-ha-border'}`} title={isConfigured ? 'Configured' : 'Not configured'} />
                  </span>
                }
              >
                <input
                  type="password"
                  value={currentValue}
                  onChange={e => setKeyValues(prev => ({ ...prev, [field.key]: e.target.value }))}
                  placeholder={isConfigured ? '••••••••••••••••' : field.placeholder}
                  autoComplete="new-password"
                  className="rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text font-mono focus:outline-none focus:ring-2 focus:ring-ha-blue"
                />
              </Field>
            )
          })}
        </div>
      </Section>

      {/* ── Save button ─────────────────────────────────────────────── */}
      <div className="flex items-center gap-4 pt-1">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-6 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue"
        >
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
        <p className="text-xs text-ha-muted">
          Restart the add-on after saving to apply LLM provider changes.
        </p>
      </div>
    </div>
  )
}
