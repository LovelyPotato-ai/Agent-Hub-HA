import { useState } from 'react'
import { ChatTab } from './components/ChatTab'
import { WorkflowRunTab } from './components/WorkflowRunTab'
import { AgentsTab } from './components/AgentsTab'
import { WorkflowsTab } from './components/WorkflowsTab'
import { SettingsPanel } from './components/SettingsPanel'

type Tab = 'chat' | 'run' | 'agents' | 'builder' | 'settings'

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'chat',     label: 'Chat',     icon: '🗨️' },
  { id: 'run',      label: 'Workflows', icon: '▶' },
  { id: 'agents',   label: 'Agents',   icon: '🤖' },
  { id: 'builder',  label: 'Builder',  icon: '🔀' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('chat')

  return (
    <div className="h-dvh bg-ha-bg flex flex-col">

      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="flex-shrink-0 border-b border-ha-border bg-ha-surface px-4 py-3 flex items-center gap-3 md:px-6 md:py-4">
        <svg className="w-7 h-7 text-ha-blue flex-shrink-0" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2M7 14a1 1 0 0 0-1 1 1 1 0 0 0 1 1 1 1 0 0 0 1-1 1 1 0 0 0-1-1m10 0a1 1 0 0 0-1 1 1 1 0 0 0 1 1 1 1 0 0 0 1-1 1 1 0 0 0-1-1m-5 3l-2 3h8l-2-3h-4z" />
        </svg>
        <div>
          <h1 className="text-base font-semibold text-ha-text leading-tight md:text-lg">AI Hub</h1>
          <p className="text-xs text-ha-muted">Multi-Agent Orchestrator · Home Assistant</p>
        </div>
      </header>

      {/* ── Desktop tab bar (hidden on mobile) ─────────────────────── */}
      <nav
        className="hidden md:flex flex-shrink-0 border-b border-ha-border bg-ha-surface px-6 gap-1"
        aria-label="Main navigation"
      >
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
      <main className={`flex-1 min-h-0 w-full ${activeTab === 'chat' ? 'overflow-hidden' : 'p-4 pb-20 md:p-6 md:pb-6 max-w-7xl mx-auto overflow-auto'}`}>
        {activeTab === 'chat' && <ChatTab />}

        {activeTab !== 'chat' && (
          <>
            {activeTab === 'run' && (
              <div>
                <div className="mb-5">
                  <h2 className="text-base font-semibold text-ha-text">Run Workflow</h2>
                  <p className="text-sm text-ha-muted mt-1">Select a workflow, enter a prompt, and run it.</p>
                </div>
                <WorkflowRunTab />
              </div>
            )}

            {activeTab === 'agents' && <AgentsTab />}

            {activeTab === 'builder' && <WorkflowsTab />}

            {activeTab === 'settings' && (
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
          </>
        )}
      </main>

      {/* ── Mobile bottom navigation bar (hidden on desktop) ───────── */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-50 flex md:hidden border-t border-ha-border bg-ha-surface"
        aria-label="Mobile navigation"
      >
        {TABS.map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={[
              'flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue focus-visible:ring-inset',
              activeTab === tab.id
                ? 'text-ha-blue'
                : 'text-ha-muted',
            ].join(' ')}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            <span className="text-lg leading-none" aria-hidden="true">{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      {/* ── Footer (desktop only) ───────────────────────────────────── */}
      <footer className="hidden md:block flex-shrink-0 border-t border-ha-border px-6 py-3 text-center text-xs text-ha-muted">
        AI Hub · Home Assistant Add-on · CrewAI · v1.3.4
      </footer>
    </div>
  )
}
