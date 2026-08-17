import { useState } from 'react'
import { AgentsTab } from './components/AgentsTab'
import { WorkflowsTab } from './components/WorkflowsTab'
import { RunTab } from './components/RunTab'
import { SettingsPanel } from './components/SettingsPanel'

type Tab = 'run' | 'agents' | 'workflows' | 'settings'

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'run',       label: 'Run',       icon: '▶' },
  { id: 'agents',    label: 'Agents',    icon: '🤖' },
  { id: 'workflows', label: 'Workflows', icon: '🔀' },
  { id: 'settings',  label: 'Settings',  icon: '⚙️' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('run')

  return (
    <div className="min-h-screen bg-ha-bg flex flex-col">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="border-b border-ha-border bg-ha-surface px-6 py-4 flex items-center gap-3">
        <svg className="w-7 h-7 text-ha-blue flex-shrink-0" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M7 14a1 1 0 0 0-1 1 1 1 0 0 0 1 1 1 1 0 0 0 1-1 1 1 0 0 0-1-1m10 0a1 1 0 0 0-1 1 1 1 0 0 0 1 1 1 1 0 0 0 1-1 1 1 0 0 0-1-1m-5 3l-2 3h8l-2-3h-4z" />
        </svg>
        <div>
          <h1 className="text-lg font-semibold text-ha-text leading-tight">AI Hub</h1>
          <p className="text-xs text-ha-muted">Multi-Agent Orchestrator · Home Assistant</p>
        </div>
      </header>

      {/* ── Tab bar ────────────────────────────────────────────────── */}
      <nav className="border-b border-ha-border bg-ha-surface px-6 flex gap-1" aria-label="Main navigation">
        {TABS.map(tab => (
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
        {activeTab === 'run'       && <RunTab />}
        {activeTab === 'agents'    && <AgentsTab />}
        {activeTab === 'workflows' && <WorkflowsTab />}
        {activeTab === 'settings'  && (
          <div className="max-w-2xl">
            <div className="mb-5">
              <h2 className="text-base font-semibold text-ha-text">Settings</h2>
              <p className="text-sm text-ha-muted mt-1">
                Configure LLM providers, API keys, and GitHub integration.
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
