/**
 * StatusFeed.tsx — Live agent log stream
 * ========================================
 * Displays a scrolling list of agent step messages received via WebSocket.
 * Auto-scrolls to the bottom when new messages arrive.
 * Shows a pulsing "thinking" indicator while the crew is running.
 */

import { useEffect, useRef, type FC } from 'react'

interface StatusFeedProps {
  messages: string[]
  isRunning: boolean
}

export const StatusFeed: FC<StatusFeedProps> = ({ messages, isRunning }) => {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div
      className="h-48 overflow-y-auto rounded-lg bg-ha-bg border border-ha-border p-3 font-mono text-xs"
      role="log"
      aria-live="polite"
      aria-label="Agent activity log"
    >
      {messages.length === 0 && !isRunning ? (
        <p className="text-ha-muted italic">No activity yet.</p>
      ) : (
        <>
          {messages.map((msg, i) => (
            <div key={i} className="text-ha-text leading-relaxed mb-0.5">
              <span className="text-ha-muted select-none mr-2">›</span>
              {msg}
            </div>
          ))}

          {/* Pulsing "thinking" indicator */}
          {isRunning && (
            <div className="flex items-center gap-1.5 mt-1 text-yellow-400">
              <span className="select-none">›</span>
              <span className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1 h-1 rounded-full bg-yellow-400 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                    aria-hidden="true"
                  />
                ))}
              </span>
              <span className="italic">Agents working…</span>
            </div>
          )}
        </>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
