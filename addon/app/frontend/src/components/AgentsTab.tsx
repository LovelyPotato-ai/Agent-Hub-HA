/**
 * AgentsTab.tsx — Agent CRUD editor
 * Lists all agents, allows creating, editing, and deleting them.
 */

import { useCallback, useEffect, useState, type FC } from 'react'
import {
  createAgent, deleteAgent, listAgents, listTools, updateAgent,
  type AgentCreate, type AgentDef, type ToolDef,
} from '../api/aiHubClient'

// ---------------------------------------------------------------------------
// Agent form
// ---------------------------------------------------------------------------

interface AgentFormProps {
  initial?: AgentDef | null
  tools: ToolDef[]
  onSave: (agent: AgentDef) => void
  onCancel: () => void
}

const EMPTY_FORM: AgentCreate = {
  name: '', role: '', goal: '', backstory: '',
  tools: [], llm_override: null, allow_delegation: false, max_iter: 5,
}

const AgentForm: FC<AgentFormProps> = ({ initial, tools, onSave, onCancel }) => {
  const [form, setForm] = useState<AgentCreate>(
    initial
      ? { name: initial.name, role: initial.role, goal: initial.goal,
          backstory: initial.backstory, tools: initial.tools,
          llm_override: initial.llm_override, allow_delegation: initial.allow_delegation,
          max_iter: initial.max_iter }
      : EMPTY_FORM
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const set = (key: keyof AgentCreate, value: unknown) =>
    setForm(prev => ({ ...prev, [key]: value }))

  const toggleTool = (toolId: string) =>
    set('tools', form.tools.includes(toolId)
      ? form.tools.filter(t => t !== toolId)
      : [...form.tools, toolId])

  const handleSubmit = async () => {
    if (!form.name.trim() || !form.role.trim()) {
      setError('Name and Role are required')
      return
    }
    setSaving(true)
    setError(null)
    try {
      let saved: AgentDef
      if (initial) {
        saved = await updateAgent(initial.id, form)
      } else {
        saved = await createAgent(form)
      }
      onSave(saved)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue'
  const labelCls = 'block text-sm font-medium text-ha-text mb-1'

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <div className="rounded-lg border border-red-700 bg-red-900/20 px-3 py-2 text-sm text-red-300">{error}</div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Name *</label>
          <input className={inputCls} value={form.name} onChange={e => set('name', e.target.value)} placeholder="My Agent" />
        </div>
        <div>
          <label className={labelCls}>Role *</label>
          <input className={inputCls} value={form.role} onChange={e => set('role', e.target.value)} placeholder="Senior Developer" />
        </div>
      </div>

      <div>
        <label className={labelCls}>Goal</label>
        <textarea className={inputCls} rows={2} value={form.goal} onChange={e => set('goal', e.target.value)} placeholder="What this agent is trying to achieve..." />
      </div>

      <div>
        <label className={labelCls}>Backstory</label>
        <textarea className={inputCls} rows={3} value={form.backstory} onChange={e => set('backstory', e.target.value)} placeholder="Personality, expertise, and context..." />
      </div>

      <div>
        <label className={labelCls}>Tools</label>
        <div className="flex flex-wrap gap-2">
          {tools.map(tool => (
            <button
              key={tool.id}
              type="button"
              onClick={() => toggleTool(tool.id)}
              title={tool.description}
              className={[
                'rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                form.tools.includes(tool.id)
                  ? 'border-ha-blue bg-ha-blue/20 text-ha-blue'
                  : 'border-ha-border bg-ha-bg text-ha-muted hover:border-ha-blue/50',
              ].join(' ')}
            >
              {tool.name}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Max Iterations</label>
          <input type="number" min={1} max={20} className={inputCls} value={form.max_iter}
            onChange={e => set('max_iter', parseInt(e.target.value) || 5)} />
        </div>
        <div className="flex items-end pb-1">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.allow_delegation}
              onChange={e => set('allow_delegation', e.target.checked)}
              className="w-4 h-4 rounded border-ha-border" />
            <span className="text-sm text-ha-text">Allow delegation to other agents</span>
          </label>
        </div>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={saving}
          className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-5 py-2 text-sm font-semibold disabled:opacity-50 transition-colors"
        >
          {saving ? 'Saving…' : initial ? 'Update Agent' : 'Create Agent'}
        </button>
        <button type="button" onClick={onCancel}
          className="rounded-lg border border-ha-border px-5 py-2 text-sm text-ha-muted hover:text-ha-text transition-colors">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent card
// ---------------------------------------------------------------------------

interface AgentCardProps {
  agent: AgentDef
  tools: ToolDef[]
  onEdit: () => void
  onDelete: () => void
}

const AgentCard: FC<AgentCardProps> = ({ agent, tools, onEdit, onDelete }) => {
  const toolNames = agent.tools.map(id => tools.find(t => t.id === id)?.name ?? id)
  return (
    <div className="card flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ha-text">{agent.name}</h3>
          <p className="text-xs text-ha-blue mt-0.5">{agent.role}</p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button onClick={onEdit} className="text-xs text-ha-muted hover:text-ha-text px-2 py-1 rounded border border-ha-border hover:border-ha-blue/50 transition-colors">Edit</button>
          <button onClick={onDelete} className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-800/50 hover:border-red-600 transition-colors">Delete</button>
        </div>
      </div>
      {agent.goal && <p className="text-xs text-ha-muted line-clamp-2">{agent.goal}</p>}
      <div className="flex flex-wrap gap-1 mt-1">
        {toolNames.map(name => (
          <span key={name} className="rounded-full bg-ha-blue/10 border border-ha-blue/30 px-2 py-0.5 text-xs text-ha-blue">{name}</span>
        ))}
        {agent.allow_delegation && (
          <span className="rounded-full bg-yellow-400/10 border border-yellow-400/30 px-2 py-0.5 text-xs text-yellow-400">delegation</span>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main tab
// ---------------------------------------------------------------------------

export const AgentsTab: FC = () => {
  const [agents, setAgents] = useState<AgentDef[]>([])
  const [tools, setTools] = useState<ToolDef[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<AgentDef | null | 'new'>('new')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [a, t] = await Promise.all([listAgents(), listTools()])
      setAgents(a)
      setTools(t)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = (saved: AgentDef) => {
    setAgents(prev => {
      const idx = prev.findIndex(a => a.id === saved.id)
      return idx >= 0 ? prev.map((a, i) => i === idx ? saved : a) : [...prev, saved]
    })
    setEditing(null)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this agent?')) return
    try {
      await deleteAgent(id)
      setAgents(prev => prev.filter(a => a.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-ha-muted gap-3">
      <svg className="w-5 h-5 animate-spin text-ha-blue" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
      Loading agents…
    </div>
  )

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-ha-text">Agents</h2>
          <p className="text-sm text-ha-muted mt-0.5">Create and manage AI agents with custom roles, goals, and tools.</p>
        </div>
        {editing !== 'new' && (
          <button
            onClick={() => setEditing('new')}
            className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-4 py-2 text-sm font-semibold transition-colors"
          >
            + New Agent
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-700 bg-red-900/20 px-4 py-3 text-sm text-red-300">{error}</div>
      )}

      {editing === 'new' && (
        <div className="card">
          <h3 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-4">New Agent</h3>
          <AgentForm tools={tools} onSave={handleSave} onCancel={() => setEditing(null)} />
        </div>
      )}

      {editing && editing !== 'new' && (
        <div className="card">
          <h3 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-4">Edit Agent</h3>
          <AgentForm initial={editing} tools={tools} onSave={handleSave} onCancel={() => setEditing(null)} />
        </div>
      )}

      {agents.length === 0 && !editing ? (
        <div className="card text-center py-12 text-ha-muted">
          <p className="text-sm">No agents yet. Create your first agent above.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {agents.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              tools={tools}
              onEdit={() => setEditing(agent)}
              onDelete={() => handleDelete(agent.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
