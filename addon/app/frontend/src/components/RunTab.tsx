/**
 * RunTab.tsx — Run agents or workflows with a prompt
 * Replaces the old Hub tab with a unified run interface.
 */

import { useCallback, useEffect, useState, type FC } from 'react'
import {
  listAgents, listWorkflows, runAgent, runWorkflow,
  type AgentDef, type WorkflowDef,
} from '../api/aiHubClient'
import { ResultPanel } from './ResultPanel'
import { StatusBadge } from './StatusBadge'
import { StatusFeed } from './StatusFeed'
import { useCrewStatus } from '../hooks/useCrewStatus'

type RunTarget = { type: 'workflow'; id: string; name: string } | { type: 'agent'; id: string; name: string }

export const RunTab: FC = () => {
  const [workflows, setWorkflows] = useState<WorkflowDef[]>([])
  const [agents, setAgents] = useState<AgentDef[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<RunTarget | null>(null)
  const [prompt, setPrompt] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)

  const { status, messages, result, error } = useCrewStatus(jobId)

  // Sync isRunning with WS status
  useEffect(() => {
    if (status === 'running') setIsRunning(true)
    if (status === 'done' || status === 'error') setIsRunning(false)
  }, [status])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [w, a] = await Promise.all([listWorkflows(), listAgents()])
      setWorkflows(w)
      setAgents(a)
      // Auto-select first workflow only if nothing is selected yet.
      // Use functional setter to read the latest `selected` without capturing
      // it in the closure (avoids stale-closure bug with empty dep array).
      setSelected(prev => (prev === null && w.length > 0)
        ? { type: 'workflow', id: w[0].id, name: w[0].name }
        : prev
      )
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleRun = async () => {
    if (!selected || !prompt.trim()) return
    setSubmitError(null)
    setJobId(null)
    setIsRunning(true)
    try {
      let resp
      if (selected.type === 'workflow') {
        resp = await runWorkflow(selected.id, prompt.trim())
      } else {
        resp = await runAgent(selected.id, prompt.trim())
      }
      setJobId(resp.job_id)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to start')
      setIsRunning(false)
    }
  }

  const inputCls = 'w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text focus:outline-none focus:ring-2 focus:ring-ha-blue'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

      {/* Left: controls */}
      <section className="flex flex-col gap-5">

        {/* Target selector */}
        <div className="card">
          <h2 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-4">Select Target</h2>

          {loading ? (
            <p className="text-sm text-ha-muted">Loading…</p>
          ) : (
            <div className="flex flex-col gap-2">
              {workflows.length > 0 && (
                <>
                  <p className="text-xs text-ha-muted font-medium uppercase tracking-wider">Workflows</p>
                  {workflows.map(wf => (
                    <button
                      key={wf.id}
                      type="button"
                      onClick={() => setSelected({ type: 'workflow', id: wf.id, name: wf.name })}
                      className={[
                        'w-full text-left rounded-lg border px-4 py-3 transition-all',
                        selected?.id === wf.id
                          ? 'border-ha-blue bg-ha-blue/10'
                          : 'border-ha-border bg-ha-bg hover:border-ha-blue/50',
                      ].join(' ')}
                    >
                      <div className={`text-sm font-semibold ${selected?.id === wf.id ? 'text-ha-blue' : 'text-ha-text'}`}>
                        {wf.name}
                      </div>
                      <div className="text-xs text-ha-muted mt-0.5">
                        {wf.process} · {wf.tasks.length} task{wf.tasks.length !== 1 ? 's' : ''}
                        {wf.description ? ` · ${wf.description}` : ''}
                      </div>
                    </button>
                  ))}
                </>
              )}

              {agents.length > 0 && (
                <>
                  <p className="text-xs text-ha-muted font-medium uppercase tracking-wider mt-2">Single Agents</p>
                  {agents.map(ag => (
                    <button
                      key={ag.id}
                      type="button"
                      onClick={() => setSelected({ type: 'agent', id: ag.id, name: ag.name })}
                      className={[
                        'w-full text-left rounded-lg border px-4 py-3 transition-all',
                        selected?.id === ag.id
                          ? 'border-ha-blue bg-ha-blue/10'
                          : 'border-ha-border bg-ha-bg hover:border-ha-blue/50',
                      ].join(' ')}
                    >
                      <div className={`text-sm font-semibold ${selected?.id === ag.id ? 'text-ha-blue' : 'text-ha-text'}`}>
                        {ag.name}
                      </div>
                      <div className="text-xs text-ha-muted mt-0.5">{ag.role}</div>
                    </button>
                  ))}
                </>
              )}

              {workflows.length === 0 && agents.length === 0 && (
                <p className="text-sm text-ha-muted">No workflows or agents yet. Create some in the Agents and Workflows tabs.</p>
              )}
            </div>
          )}
        </div>

        {/* Prompt */}
        <div className="card flex-1">
          <h2 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-4">Prompt</h2>
          <div className="relative">
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder={selected ? `Enter your request for ${selected.name}…` : 'Select a target above first'}
              disabled={isRunning || !selected}
              rows={6}
              className={[inputCls, 'resize-none', (!selected || isRunning) ? 'opacity-50 cursor-not-allowed' : ''].join(' ')}
            />
            <span className="absolute bottom-2 right-3 text-xs text-ha-muted">{prompt.length}</span>
          </div>

          {submitError && (
            <p className="mt-3 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">{submitError}</p>
          )}

          <button
            type="button"
            onClick={handleRun}
            disabled={isRunning || !selected || !prompt.trim()}
            className={[
              'mt-4 w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-all',
              (isRunning || !selected || !prompt.trim())
                ? 'bg-ha-border text-ha-muted cursor-not-allowed'
                : 'bg-ha-blue hover:bg-ha-blue-dark text-white cursor-pointer',
            ].join(' ')}
          >
            {isRunning ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Running…
              </span>
            ) : `Run ${selected?.type === 'agent' ? 'Agent' : 'Workflow'}`}
          </button>
        </div>

        {/* Live log */}
        {(isRunning || messages.length > 0) && (
          <div className="card">
            <h2 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-3">Agent Log</h2>
            <StatusFeed messages={messages} isRunning={isRunning} />
          </div>
        )}
      </section>

      {/* Right: result */}
      <section className="flex flex-col gap-5">
        <div className="card flex-1 min-h-[400px]">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-ha-muted uppercase tracking-wider">Result</h2>
            <StatusBadge status={status} />
          </div>
          <ResultPanel result={result} error={error} isRunning={isRunning} jobId={jobId} />
        </div>
      </section>
    </div>
  )
}
