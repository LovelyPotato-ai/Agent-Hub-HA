/**
 * ChatTab.tsx — Agent chat interface
 * Shows a grid of agent cards; selecting one opens a full-screen chat.
 * Uses runAgent() + useCrewStatus() for real-time responses.
 */

import { useCallback, useEffect, useRef, useState, type FC, type KeyboardEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { listAgents, runAgent, type AgentDef } from '../api/aiHubClient'
import { useCrewStatus } from '../hooks/useCrewStatus'

// ---------------------------------------------------------------------------
// Role → avatar colour mapping
// ---------------------------------------------------------------------------

const ROLE_COLOURS: Record<string, string> = {
  analyst:    'bg-purple-600',
  researcher: 'bg-blue-600',
  writer:     'bg-green-600',
  coder:      'bg-orange-600',
  reviewer:   'bg-red-600',
  manager:    'bg-yellow-600',
  assistant:  'bg-teal-600',
}

function avatarColour(role: string): string {
  const key = role.toLowerCase().split(/\s+/)[0]
  return ROLE_COLOURS[key] ?? 'bg-ha-blue'
}

// ---------------------------------------------------------------------------
// Message types
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  timestamp: Date
}

// ---------------------------------------------------------------------------
// Agent card
// ---------------------------------------------------------------------------

interface AgentCardProps {
  agent: AgentDef
  onSelect: (agent: AgentDef) => void
}

const AgentCard: FC<AgentCardProps> = ({ agent, onSelect }) => {
  const initial = agent.name.charAt(0).toUpperCase()
  const colour  = avatarColour(agent.role)

  return (
    <button
      type="button"
      onClick={() => onSelect(agent)}
      className="flex flex-col items-center gap-3 rounded-xl border border-ha-border bg-ha-surface p-5 text-center transition-all hover:border-ha-blue hover:bg-ha-blue/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue"
    >
      {/* Avatar */}
      <div className={`flex h-14 w-14 items-center justify-center rounded-full text-xl font-bold text-white ${colour}`}>
        {initial}
      </div>

      {/* Name */}
      <div className="w-full">
        <p className="text-sm font-semibold text-ha-text truncate">{agent.name}</p>
        <p className="mt-0.5 text-xs text-ha-muted truncate">{agent.role}</p>
      </div>

      {/* Tool badges */}
      {agent.tools.length > 0 && (
        <div className="flex flex-wrap justify-center gap-1">
          {agent.tools.slice(0, 3).map(t => (
            <span key={t} className="rounded-full border border-ha-border px-2 py-0.5 text-[10px] text-ha-muted">
              {t}
            </span>
          ))}
          {agent.tools.length > 3 && (
            <span className="rounded-full border border-ha-border px-2 py-0.5 text-[10px] text-ha-muted">
              +{agent.tools.length - 3}
            </span>
          )}
        </div>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Typing indicator
// ---------------------------------------------------------------------------

const TypingIndicator: FC = () => (
  <div className="max-w-[80%]">
    <div className="rounded-2xl rounded-bl-sm border border-ha-border bg-ha-surface px-4 py-3">
      <div className="flex gap-1">
        <span className="h-2 w-2 rounded-full bg-ha-muted animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="h-2 w-2 rounded-full bg-ha-muted animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="h-2 w-2 rounded-full bg-ha-muted animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  </div>
)

// ---------------------------------------------------------------------------
// Chat bubble
// ---------------------------------------------------------------------------

interface BubbleProps {
  message: ChatMessage
  agentInitial: string
  agentColour: string
}

const Bubble: FC<BubbleProps> = ({ message, agentInitial, agentColour }) => {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="max-w-[80%] ml-auto">
        <div className="rounded-2xl rounded-br-sm bg-ha-blue px-4 py-2 text-sm text-white">
          {message.content}
        </div>
        <p className="mt-1 text-right text-[10px] text-ha-muted">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    )
  }

  return (
    <div className="flex items-end gap-2">
      <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${agentColour}`}>
        {agentInitial}
      </div>
      <div className="max-w-[80%]">
        <div className="rounded-2xl rounded-bl-sm border border-ha-border bg-ha-surface px-4 py-2 text-sm text-ha-text prose-ha">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
        <p className="mt-1 text-[10px] text-ha-muted">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chat view (full-screen when agent selected)
// ---------------------------------------------------------------------------

interface ChatViewProps {
  agent: AgentDef
  onBack: () => void
}

const ChatView: FC<ChatViewProps> = ({ agent, onBack }) => {
  const [messages, setMessages]   = useState<ChatMessage[]>([])
  const [input, setInput]         = useState('')
  const [jobId, setJobId]         = useState<string | null>(null)
  const [isWaiting, setIsWaiting] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const bottomRef                 = useRef<HTMLDivElement>(null)
  const textareaRef               = useRef<HTMLTextAreaElement>(null)

  const { status, result, error } = useCrewStatus(jobId)

  const colour  = avatarColour(agent.role)
  const initial = agent.name.charAt(0).toUpperCase()

  // When the WS delivers a result, append the agent message
  useEffect(() => {
    if (status === 'done' && result !== null) {
      setMessages(prev => [...prev, {
        id:        crypto.randomUUID(),
        role:      'agent',
        content:   result,
        timestamp: new Date(),
      }])
      setIsWaiting(false)
      setJobId(null)
    }
    if (status === 'error' && error !== null) {
      setMessages(prev => [...prev, {
        id:        crypto.randomUUID(),
        role:      'agent',
        content:   `❌ Error: ${error}`,
        timestamp: new Date(),
      }])
      setIsWaiting(false)
      setJobId(null)
    }
  }, [status, result, error])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isWaiting])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isWaiting) return

    setSendError(null)
    setInput('')
    setMessages(prev => [...prev, {
      id:        crypto.randomUUID(),
      role:      'user',
      content:   text,
      timestamp: new Date(),
    }])
    setIsWaiting(true)

    try {
      const resp = await runAgent(agent.id, text)
      setJobId(resp.job_id)
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Failed to send')
      setIsWaiting(false)
    }
  }, [input, isWaiting, agent.id])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Auto-resize textarea
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <div className="flex h-full flex-col">

      {/* ── Chat header ─────────────────────────────────────────────── */}
      <div className="flex flex-shrink-0 items-center gap-3 border-b border-ha-border bg-ha-surface px-4 py-3">
        <button
          type="button"
          onClick={onBack}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-ha-border text-ha-muted transition-colors hover:border-ha-blue hover:text-ha-blue focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue"
          aria-label="Back to agent list"
        >
          ←
        </button>

        <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${colour}`}>
          {initial}
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-ha-text truncate">{agent.name}</p>
          <p className="text-xs text-ha-muted truncate">{agent.role}</p>
        </div>

        {isWaiting && (
          <span className="flex items-center gap-1.5 text-xs text-ha-blue">
            <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Thinking…
          </span>
        )}
      </div>

      {/* ── Message list ────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && !isWaiting && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <div className={`flex h-16 w-16 items-center justify-center rounded-full text-2xl font-bold text-white ${colour}`}>
              {initial}
            </div>
            <p className="text-sm font-semibold text-ha-text">{agent.name}</p>
            <p className="text-xs text-ha-muted max-w-xs">{agent.goal || `Chat with ${agent.name}. Type a message to get started.`}</p>
          </div>
        )}

        {messages.map(msg => (
          <Bubble
            key={msg.id}
            message={msg}
            agentInitial={initial}
            agentColour={colour}
          />
        ))}

        {isWaiting && <TypingIndicator />}

        {sendError && (
          <p className="rounded-lg border border-red-800 bg-red-900/20 px-3 py-2 text-sm text-red-400">
            {sendError}
          </p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input area ──────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-ha-border bg-ha-surface px-4 pt-3 pb-20 md:pb-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${agent.name}… (Enter to send, Shift+Enter for newline)`}
            disabled={isWaiting}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-ha-border bg-ha-bg px-4 py-2.5 text-sm text-ha-text placeholder:text-ha-muted focus:outline-none focus:ring-2 focus:ring-ha-blue disabled:opacity-50"
            style={{ minHeight: '42px', maxHeight: '160px' }}
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={isWaiting || !input.trim()}
            className="flex h-[42px] w-[42px] flex-shrink-0 items-center justify-center rounded-xl bg-ha-blue text-white transition-all hover:bg-ha-blue-dark disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue"
            aria-label="Send message"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ChatTab — top-level component
// ---------------------------------------------------------------------------

export const ChatTab: FC = () => {
  const [agents, setAgents]         = useState<AgentDef[]>([])
  const [loading, setLoading]       = useState(true)
  const [loadError, setLoadError]   = useState<string | null>(null)
  const [selected, setSelected]     = useState<AgentDef | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const data = await listAgents()
      setAgents(data)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load agents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // ── Agent selected → show chat ──────────────────────────────────────────
  if (selected) {
    return <ChatView agent={selected} onBack={() => setSelected(null)} />
  }

  // ── No agent selected → show grid ──────────────────────────────────────
  return (
    <div className="h-full overflow-y-auto p-4 pb-20 md:p-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">
        <div>
          <h2 className="text-base font-semibold text-ha-text">Chat with an Agent</h2>
          <p className="mt-1 text-sm text-ha-muted">Select an agent to start a conversation.</p>
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-sm text-ha-muted">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Loading agents…
          </div>
        )}

        {loadError && (
          <p className="rounded-lg border border-red-800 bg-red-900/20 px-3 py-2 text-sm text-red-400">
            {loadError}
          </p>
        )}

        {!loading && !loadError && agents.length === 0 && (
          <div className="rounded-xl border border-ha-border bg-ha-surface p-8 text-center">
            <p className="text-sm text-ha-muted">No agents yet.</p>
            <p className="mt-1 text-xs text-ha-muted">Create agents in the <strong className="text-ha-text">Agents</strong> tab first.</p>
          </div>
        )}

        {!loading && agents.length > 0 && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
            {agents.map(agent => (
              <AgentCard key={agent.id} agent={agent} onSelect={setSelected} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
