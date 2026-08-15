import { useState } from 'react'
import { CrewSelector, type CrewId } from './components/CrewSelector'
import { PromptInput } from './components/PromptInput'
import { StatusBadge } from './components/StatusBadge'
import { StatusFeed } from './components/StatusFeed'
import { ResultPanel } from './components/ResultPanel'
import { SettingsPanel } from './components/SettingsPanel'
import { useCrewStatus } from './hooks/useCrewStatus'
import { triggerCrew } from './api/aiHubClient'

type Tab = 'hub' | 'settings'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('hub')
  const [selectedCrew, setSelectedCrew] = useState<CrewId>('code_review')
  const [jobId, setJobId] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const { status, messages, result, error } = useCrewStatus(jobId)

  const isRunning = status === 'running'

  async function handleSubmit(crew: CrewId, prompt: string, options: Record<string, unknown>) {
    setSubmitError(null)
    setJobId(null)

    try {
      const { job_id } = await triggerCrew({ crew, prompt, options })
      setJobId(job_id)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to trigger crew')
    }
  }

  return (
    <div className="min-h-screen bg-ha-bg flex flex-col">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="border-b border-ha-border bg-ha-surface px-6 py-4 flex items-center gap-3">
        <svg
          className="w-7 h-7 text-ha-blue flex-shrink-0"
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M7 14a1 1 0 0 0-1 1 1 1 0 0 0 1 1 1 1 0 0 0 1-1 1 1 0 0 0-1-1m10 0a1 1 0 0 0-1 1 1 1 0 0 0 1 1 1 1 0 0 0 1-1 1 1 0 0 0-1-1m-5 3l-2 3h8l-2-3h-4z" />
        </svg>
        <div>
          <h1 className="text-lg font-semibold text-ha-text leading-tight">AI Hub</h1>
          <p className="text-xs text-ha-muted">Multi-Agent Orchestrator · Home Assistant</p>
        </div>
        <div className="ml-auto flex items-center gap-4">
          <StatusBadge status={status} />
        </div>
      </header>

      {/* ── Tab bar ────────────────────────────────────────────────── */}
      <nav className="border-b border-ha-border bg-ha-surface px-6 flex gap-1" aria-label="Main navigation">
        {([
          { id: 'hub' as Tab, label: 'Hub', icon: '🤖' },
          { id: 'settings' as Tab, label: 'Settings', icon: '⚙️' },
        ] as const).map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={[
              'flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue',
              activeTab === tab.id
                ? 'border-ha-blue text-ha-blue'
                : 'border-transparent text-ha-muted hover:text-ha-text hover:border-ha-border',
            ].join(' ')}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            <span aria-hidden="true">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      {/* ── Main content ───────────────────────────────────────────── */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">

        {/* Hub tab */}
        {activeTab === 'hub' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Left column: controls */}
            <section className="flex flex-col gap-5">
              <div className="card">
                <h2 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-4">
                  Select Crew
                </h2>
                <CrewSelector value={selectedCrew} onChange={setSelectedCrew} disabled={isRunning} />
              </div>

              <div className="card flex-1">
                <h2 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-4">
                  Prompt
                </h2>
                <PromptInput
                  crew={selectedCrew}
                  onSubmit={handleSubmit}
                  disabled={isRunning}
                />
                {submitError && (
                  <p className="mt-3 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
                    {submitError}
                  </p>
                )}
              </div>

              {/* Live status feed */}
              {(isRunning || messages.length > 0) && (
                <div className="card">
                  <h2 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-3">
                    Agent Log
                  </h2>
                  <StatusFeed messages={messages} isRunning={isRunning} />
                </div>
              )}
            </section>

            {/* Right column: result */}
            <section className="flex flex-col gap-5">
              <div className="card flex-1 min-h-[400px]">
                <h2 className="text-sm font-semibold text-ha-muted uppercase tracking-wider mb-4">
                  Result
                </h2>
                <ResultPanel
                  result={result}
                  error={error}
                  isRunning={isRunning}
                  jobId={jobId}
                />
              </div>
            </section>
          </div>
        )}

        {/* Settings tab */}
        {activeTab === 'settings' && (
          <div className="max-w-2xl">
            <div className="mb-5">
              <h2 className="text-base font-semibold text-ha-text">Settings</h2>
              <p className="text-sm text-ha-muted mt-1">
                Configure LLM providers, per-agent model overrides, API keys, and GitHub integration.
              </p>
            </div>
            <SettingsPanel />
          </div>
        )}
      </main>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer className="border-t border-ha-border px-6 py-3 text-center text-xs text-ha-muted">
        AI Hub · Home Assistant Add-on · CrewAI
      </footer>
    </div>
  )
}
