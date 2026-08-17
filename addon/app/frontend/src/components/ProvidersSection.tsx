/**
 * ProvidersSection.tsx — LLM Provider management
 * ================================================
 * Lists all providers, allows adding custom providers (openai_compatible,
 * gemini, anthropic), editing model lists, and deleting custom providers.
 * Also supports live model discovery via the provider's models API and
 * editing API keys directly inside the provider form.
 */

import { useCallback, useEffect, useState, type FC } from 'react'
import {
  createProvider, deleteProvider, fetchProviderModels, getSettings, listProviders,
  saveSettings, updateProvider,
  type ProviderDef, type SettingsPayload,
} from '../api/aiHubClient'

const inputCls = 'w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue'
const labelCls = 'block text-xs text-ha-muted mb-1'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function apiKeyPlaceholder(provider: ProviderDef): string {
  const id = provider.id.toLowerCase()
  if (id === 'openai') return 'sk-...'
  if (id === 'gemini') return 'AIza...'
  if (id === 'anthropic') return 'sk-ant-...'
  if (id === 'openrouter') return 'sk-or-...'
  return ''
}

// ---------------------------------------------------------------------------
// Provider form (create/edit)
// ---------------------------------------------------------------------------

interface ProviderFormProps {
  initial?: ProviderDef | null
  keysConfigured: Record<string, boolean>
  onSave: (p: ProviderDef) => void
  onCancel: () => void
}

const ProviderForm: FC<ProviderFormProps> = ({ initial, keysConfigured, onSave, onCancel }) => {
  const [name, setName] = useState(initial?.name ?? '')
  const [type, setType] = useState<'openai' | 'openai_compatible' | 'gemini' | 'anthropic'>(initial?.type ?? 'openai_compatible')
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? '')
  const [modelsText, setModelsText] = useState((initial?.models ?? []).join(', '))
  const [apiKeyValue, setApiKeyValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const apiKeyField = initial?.api_key_field ?? ''
  const apiKeyConfigured = !!apiKeyField && !!keysConfigured[apiKeyField]

  const handleSave = async () => {
    if (!name.trim()) { setError('Name is required'); return }
    if (type === 'openai_compatible' && !baseUrl.trim()) { setError('Base URL is required for OpenAI-compatible providers'); return }
    setSaving(true)
    setError(null)
    try {
      const models = modelsText.split(',').map(m => m.trim()).filter(Boolean)
      let saved: ProviderDef
      if (initial) {
        saved = await updateProvider(initial.id, { name, type, base_url: baseUrl, models })
      } else {
        saved = await createProvider({ name, type, base_url: baseUrl, api_key_field: '', models })
      }
      if (apiKeyField && apiKeyValue.trim()) {
        await saveSettings({ [apiKeyField]: apiKeyValue.trim() } as unknown as Partial<SettingsPayload>)
      }
      onSave(saved)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <div className="rounded-lg border border-red-700 bg-red-900/20 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div>
        <label className={labelCls}>Provider Name *</label>
        <input className={inputCls} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Local Ollama" />
      </div>

      <div>
        <label className={labelCls}>Type</label>
        <select className={inputCls} value={type} onChange={e => setType(e.target.value as typeof type)}
          disabled={!!initial && initial.builtin}>
          <option value="openai_compatible">OpenAI-compatible (Ollama, LM Studio, vLLM, etc.)</option>
          <option value="gemini">Google Gemini</option>
          <option value="anthropic">Anthropic Claude</option>
        </select>
        {initial?.builtin && <p className="text-xs text-ha-muted mt-1">Type cannot be changed for built-in providers.</p>}
      </div>

      {type === 'openai_compatible' && (
        <div>
          <label className={labelCls}>Base URL *</label>
          <input className={inputCls} value={baseUrl} onChange={e => setBaseUrl(e.target.value)}
            placeholder="http://localhost:11434/v1" />
        </div>
      )}

      {apiKeyField && initial && (
        <div>
          <label className={labelCls}>
            <span className="flex items-center gap-2">
              {initial.name} API Key
              <span className={`w-2 h-2 rounded-full inline-block ${apiKeyConfigured ? 'bg-green-400' : 'bg-ha-border'}`}
                title={apiKeyConfigured ? 'Configured' : 'Not configured'} />
            </span>
          </label>
          <input
            type="password"
            value={apiKeyValue}
            onChange={e => setApiKeyValue(e.target.value)}
            placeholder={apiKeyConfigured ? '••••••••••••••••' : apiKeyPlaceholder(initial)}
            autoComplete="new-password"
            className={`${inputCls} font-mono`}
          />
        </div>
      )}

      <div>
        <label className={labelCls}>Models (comma-separated)</label>
        <textarea className={inputCls} rows={2} value={modelsText} onChange={e => setModelsText(e.target.value)}
          placeholder="llama3.2, mistral, gemma2" />
      </div>

      <div className="flex gap-3">
        <button onClick={handleSave} disabled={saving}
          className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-5 py-2 text-sm font-semibold disabled:opacity-50 transition-colors">
          {saving ? 'Saving…' : initial ? 'Update Provider' : 'Create Provider'}
        </button>
        <button onClick={onCancel}
          className="rounded-lg border border-ha-border px-5 py-2 text-sm text-ha-muted hover:text-ha-text transition-colors">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Provider card
// ---------------------------------------------------------------------------

interface ProviderCardProps {
  provider: ProviderDef
  onEdit: () => void
  onDelete: () => void
  onFetchModels: () => void
  fetching: boolean
  fetchError: string | null
}

const TYPE_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  openai_compatible: 'OpenAI-compatible',
  gemini: 'Gemini',
  anthropic: 'Anthropic',
}

const ProviderCard: FC<ProviderCardProps> = ({ provider, onEdit, onDelete, onFetchModels, fetching, fetchError }) => (
  <div className="rounded-xl border border-ha-border bg-ha-surface p-4 flex flex-col gap-2">
    <div className="flex items-start justify-between gap-2">
      <div>
        <h4 className="text-sm font-semibold text-ha-text">{provider.name}</h4>
        <p className="text-xs text-ha-muted mt-0.5">
          {TYPE_LABELS[provider.type] ?? provider.type}
          {provider.base_url ? ` · ${provider.base_url}` : ''}
          {provider.builtin && <span className="ml-1 text-ha-blue">(built-in)</span>}
        </p>
      </div>
      <div className="flex gap-2 flex-shrink-0">
        <button onClick={onFetchModels} disabled={fetching}
          className="inline-flex items-center gap-1 text-xs text-ha-muted hover:text-ha-text px-2 py-1 rounded border border-ha-border hover:border-ha-blue/50 transition-colors disabled:opacity-50">
          {fetching ? (
            <>
              <svg className="w-3 h-3 animate-spin text-ha-blue" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Fetching…
            </>
          ) : 'Fetch Models'}
        </button>
        <button onClick={onEdit}
          className="text-xs text-ha-muted hover:text-ha-text px-2 py-1 rounded border border-ha-border hover:border-ha-blue/50 transition-colors">
          Edit
        </button>
        {!provider.builtin && (
          <button onClick={onDelete}
            className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-800/50 hover:border-red-600 transition-colors">
            Delete
          </button>
        )}
      </div>
    </div>
    {fetchError && <div className="rounded-lg border border-red-700 bg-red-900/20 px-3 py-2 text-xs text-red-300">{fetchError}</div>}
    <div className="flex flex-wrap gap-1">
      {provider.models.map(m => (
        <span key={m} className="rounded-full bg-ha-bg border border-ha-border px-2 py-0.5 text-xs text-ha-muted">{m}</span>
      ))}
    </div>
  </div>
)

// ---------------------------------------------------------------------------
// Main section
// ---------------------------------------------------------------------------

export const ProvidersSection: FC = () => {
  const [providers, setProviders] = useState<ProviderDef[]>([])
  const [keysConfigured, setKeysConfigured] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<ProviderDef | null | 'new'>(null)
  const [fetching, setFetching] = useState<string | null>(null)
  const [fetchErrors, setFetchErrors] = useState<Record<string, string>>({})

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [providerList, settings] = await Promise.all([listProviders(), getSettings()])
      setProviders(providerList)
      setKeysConfigured(settings.keys_configured)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load providers')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = (saved: ProviderDef) => {
    setProviders(prev => {
      const idx = prev.findIndex(p => p.id === saved.id)
      return idx >= 0 ? prev.map((p, i) => i === idx ? saved : p) : [...prev, saved]
    })
    setEditing(null)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this provider?')) return
    try {
      await deleteProvider(id)
      setProviders(prev => prev.filter(p => p.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  const handleFetchModels = async (id: string) => {
    setFetching(id)
    setFetchErrors(prev => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    try {
      const result = await fetchProviderModels(id)
      await updateProvider(id, { models: result.models })
      await load()
    } catch (err) {
      setFetchErrors(prev => ({ ...prev, [id]: err instanceof Error ? err.message : 'Fetch failed' }))
    } finally {
      setFetching(null)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ha-muted">
          Manage LLM providers and models. Add your own OpenAI-compatible endpoints (Ollama, LM Studio, vLLM) or add models to existing providers.
        </p>
        {!editing && (
          <button onClick={() => setEditing('new')}
            className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-3 py-1.5 text-xs font-semibold flex-shrink-0 ml-3 transition-colors">
            + Add Provider
          </button>
        )}
      </div>

      {error && <div className="rounded-lg border border-red-700 bg-red-900/20 px-3 py-2 text-sm text-red-300">{error}</div>}

      {editing && (
        <div className="rounded-xl border border-ha-blue/40 bg-ha-bg p-4">
          <h4 className="text-sm font-semibold text-ha-text mb-3">
            {editing === 'new' ? 'Add Provider' : `Edit ${(editing as ProviderDef).name}`}
          </h4>
          <ProviderForm
            initial={editing === 'new' ? null : editing as ProviderDef}
            keysConfigured={keysConfigured}
            onSave={handleSave}
            onCancel={() => setEditing(null)}
          />
        </div>
      )}

      {loading ? (
        <p className="text-sm text-ha-muted py-4">Loading providers…</p>
      ) : (
        <div className="flex flex-col gap-2">
          {providers.map(p => (
            <ProviderCard
              key={p.id}
              provider={p}
              onEdit={() => setEditing(p)}
              onDelete={() => handleDelete(p.id)}
              onFetchModels={() => handleFetchModels(p.id)}
              fetching={fetching === p.id}
              fetchError={fetchErrors[p.id] ?? null}
            />
          ))}
        </div>
      )}
    </div>
  )
}
