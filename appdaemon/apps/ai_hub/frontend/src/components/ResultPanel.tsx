/**
 * ResultPanel.tsx — Markdown-rendered crew result display
 * =========================================================
 * Shows the final crew output rendered as Markdown with syntax highlighting.
 * Includes a copy-to-clipboard button and handles loading/error states.
 */

import { useState, type FC } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ResultPanelProps {
  result: string | null
  error: string | null
  isRunning: boolean
  jobId: string | null
}

export const ResultPanel: FC<ResultPanelProps> = ({ result, error, isRunning, jobId }) => {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    if (!result) return
    try {
      await navigator.clipboard.writeText(result)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard API not available (e.g. non-HTTPS context)
    }
  }

  // ── Loading state ──────────────────────────────────────────────────
  if (isRunning) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 text-ha-muted py-12">
        <svg
          className="w-10 h-10 animate-spin text-ha-blue"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        <div className="text-center">
          <p className="text-sm font-medium text-ha-text">Agents are working…</p>
          {jobId && <p className="text-xs text-ha-muted mt-1">Job ID: {jobId}</p>}
        </div>
      </div>
    )
  }

  // ── Error state ────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="rounded-lg border border-red-800 bg-red-900/20 p-4">
        <div className="flex items-start gap-3">
          <span className="text-red-400 text-lg flex-shrink-0" aria-hidden="true">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-400 mb-1">Crew Error</p>
            <p className="text-sm text-red-300 font-mono break-words">{error}</p>
          </div>
        </div>
      </div>
    )
  }

  // ── Empty state ────────────────────────────────────────────────────
  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-ha-muted py-12">
        <svg className="w-12 h-12 opacity-30" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm4 18H6V4h7v5h5v11z" />
        </svg>
        <p className="text-sm">Select a crew, enter a prompt, and click Run Crew.</p>
      </div>
    )
  }

  // ── Result state ───────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-ha-muted">
          {result.length.toLocaleString()} characters
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className={[
            'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all',
            'border focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue',
            copied
              ? 'border-green-600 bg-green-900/30 text-green-400'
              : 'border-ha-border bg-ha-bg text-ha-muted hover:text-ha-text hover:border-ha-blue/50',
          ].join(' ')}
          aria-label="Copy result to clipboard"
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              Copy
            </>
          )}
        </button>
      </div>

      {/* Markdown output */}
      <div className="flex-1 overflow-y-auto rounded-lg border border-ha-border bg-ha-bg p-4 prose-ha">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {result}
        </ReactMarkdown>
      </div>
    </div>
  )
}
