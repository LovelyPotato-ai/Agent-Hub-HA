/**
 * GitHubReposSection.tsx — Named GitHub connection management
 * =============================================================
 * Lists all GitHub connections, allows adding/editing/deleting them.
 * A single global PAT (managed in SettingsPanel) authenticates every
 * connection; workflow tasks select a connection via github_repo_id.
 */

import { useCallback, useEffect, useState, type FC } from 'react'
import {
  createGitHubRepo, deleteGitHubRepo, listGitHubRepos, updateGitHubRepo,
  type GitHubRepoDef,
} from '../api/aiHubClient'

const inputCls = 'w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue'
const labelCls = 'block text-xs text-ha-muted mb-1'

// ---------------------------------------------------------------------------
// Connection form (create/edit)
// ---------------------------------------------------------------------------

interface RepoFormProps {
  initial?: GitHubRepoDef | null
  onSave: (repo: GitHubRepoDef) => void
  onCancel: () => void
}

const RepoForm: FC<RepoFormProps> = ({ initial, onSave, onCancel }) => {
  const [name, setName] = useState(initial?.name ?? '')
  const [owner, setOwner] = useState(initial?.owner ?? '')
  const [repo, setRepo] = useState(initial?.repo ?? '')
  const [branch, setBranch] = useState(initial?.branch ?? 'main')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    if (!name.trim()) { setError('Name is required'); return }
    if (!owner.trim()) { setError('Repository owner is required'); return }
    if (!repo.trim()) { setError('Repository name is required'); return }
    setSaving(true)
    setError(null)
    try {
      const data = {
        name: name.trim(),
        owner: owner.trim(),
        repo: repo.trim(),
        branch: branch.trim() || 'main',
      }
      const saved = initial
        ? await updateGitHubRepo(initial.id, data)
        : await createGitHubRepo(data)
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
        <label className={labelCls}>Connection Name *</label>
        <input className={inputCls} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. HA Config" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Owner *</label>
          <input className={inputCls} value={owner} onChange={e => setOwner(e.target.value)} placeholder="myusername" />
        </div>
        <div>
          <label className={labelCls}>Repository *</label>
          <input className={inputCls} value={repo} onChange={e => setRepo(e.target.value)} placeholder="home-assistant-config" />
        </div>
      </div>

      <div>
        <label className={labelCls}>Branch</label>
        <input className={inputCls} value={branch} onChange={e => setBranch(e.target.value)} placeholder="main" />
      </div>

      <div className="flex gap-3">
        <button onClick={handleSave} disabled={saving}
          className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-5 py-2 text-sm font-semibold disabled:opacity-50 transition-colors">
          {saving ? 'Saving…' : initial ? 'Update Connection' : 'Create Connection'}
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
// Connection card
// ---------------------------------------------------------------------------

interface RepoCardProps {
  repo: GitHubRepoDef
  onEdit: () => void
  onDelete: () => void
}

const RepoCard: FC<RepoCardProps> = ({ repo, onEdit, onDelete }) => (
  <div className="rounded-xl border border-ha-border bg-ha-surface p-4 flex flex-col gap-2">
    <div className="flex items-start justify-between gap-2">
      <div>
        <h4 className="text-sm font-semibold text-ha-text">{repo.name}</h4>
        <p className="text-xs text-ha-muted mt-0.5">
          {repo.owner}/{repo.repo} · <span className="text-ha-blue">@{repo.branch}</span>
        </p>
      </div>
      <div className="flex gap-2 flex-shrink-0">
        <button onClick={onEdit}
          className="text-xs text-ha-muted hover:text-ha-text px-2 py-1 rounded border border-ha-border hover:border-ha-blue/50 transition-colors">
          Edit
        </button>
        <button onClick={onDelete}
          className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-800/50 hover:border-red-600 transition-colors">
          Delete
        </button>
      </div>
    </div>
  </div>
)

// ---------------------------------------------------------------------------
// Main section
// ---------------------------------------------------------------------------

export const GitHubReposSection: FC = () => {
  const [repos, setRepos] = useState<GitHubRepoDef[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<GitHubRepoDef | null | 'new'>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setRepos(await listGitHubRepos())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load GitHub connections')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = (saved: GitHubRepoDef) => {
    setRepos(prev => {
      const idx = prev.findIndex(r => r.id === saved.id)
      return idx >= 0 ? prev.map((r, i) => i === idx ? saved : r) : [...prev, saved]
    })
    setEditing(null)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this GitHub connection?')) return
    try {
      await deleteGitHubRepo(id)
      setRepos(prev => prev.filter(r => r.id !== id))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ha-muted">
          Manage GitHub repositories that agents can commit to. One global PAT covers all connections.
        </p>
        {!editing && (
          <button onClick={() => setEditing('new')}
            className="rounded-lg bg-ha-blue hover:bg-ha-blue-dark text-white px-3 py-1.5 text-xs font-semibold flex-shrink-0 ml-3 transition-colors">
            + Add Connection
          </button>
        )}
      </div>

      {error && <div className="rounded-lg border border-red-700 bg-red-900/20 px-3 py-2 text-sm text-red-300">{error}</div>}

      {editing && (
        <div className="rounded-xl border border-ha-blue/40 bg-ha-bg p-4">
          <h4 className="text-sm font-semibold text-ha-text mb-3">
            {editing === 'new' ? 'Add Connection' : `Edit ${(editing as GitHubRepoDef).name}`}
          </h4>
          <RepoForm
            initial={editing === 'new' ? null : editing as GitHubRepoDef}
            onSave={handleSave}
            onCancel={() => setEditing(null)}
          />
        </div>
      )}

      {loading ? (
        <p className="text-sm text-ha-muted py-4">Loading connections…</p>
      ) : repos.length === 0 ? (
        <p className="text-sm text-ha-muted py-2">No GitHub connections yet. Add one above.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {repos.map(r => (
            <RepoCard
              key={r.id}
              repo={r}
              onEdit={() => setEditing(r)}
              onDelete={() => handleDelete(r.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
