/**
 * useCrewStatus.ts — WebSocket hook for real-time crew status
 * =============================================================
 * Connects to the AI Hub WebSocket endpoint and pushes status,
 * log messages, and the final result into React state.
 *
 * Usage:
 *   const { status, messages, result, error } = useCrewStatus(jobId)
 *
 * - Pass null as jobId to stay disconnected.
 * - Pass a job_id string to subscribe to that specific job.
 * - Pass '*' to subscribe to all jobs (useful for the global status badge).
 *
 * The hook automatically reconnects if the WebSocket closes unexpectedly
 * with exponential backoff up to 30 seconds.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { createWebSocket, type HubStatus, type WsMessage } from '../api/aiHubClient'

interface CrewStatusState {
  status: HubStatus
  messages: string[]
  result: string | null
  error: string | null
}

const INITIAL_STATE: CrewStatusState = {
  status: 'idle',
  messages: [],
  result: null,
  error: null,
}

const MAX_MESSAGES = 200
const MAX_BACKOFF_MS = 30_000

export function useCrewStatus(jobId: string | null): CrewStatusState {
  const [state, setState] = useState<CrewStatusState>(INITIAL_STATE)
  const wsRef = useRef<WebSocket | null>(null)
  const backoffRef = useRef<number>(1000)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!jobId || !mountedRef.current) return

    // Reset state for a new job
    setState(INITIAL_STATE)

    const ws = createWebSocket(jobId)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      backoffRef.current = 1000 // reset backoff on successful connect
    }

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return

      let msg: WsMessage
      try {
        msg = JSON.parse(event.data as string) as WsMessage
      } catch {
        return
      }

      setState((prev: CrewStatusState) => {
        switch (msg.type) {
          case 'status':
            return {
              ...prev,
              status: msg.status,
            }

          case 'result':
            return {
              ...prev,
              status: 'done',
              result: msg.result,
              messages: [
                ...prev.messages.slice(-MAX_MESSAGES + 1),
                `✅ Crew '${msg.crew}' finished at ${new Date(msg.timestamp).toLocaleTimeString()}`,
              ],
            }

          case 'error':
            return {
              ...prev,
              status: 'error',
              error: msg.message,
              messages: [
                ...prev.messages.slice(-MAX_MESSAGES + 1),
                `❌ Error: ${msg.message}`,
              ],
            }

          default:
            return prev
        }
      })
    }

    ws.onerror = () => {
      // onerror is always followed by onclose — handle reconnect there
    }

    ws.onclose = (event: CloseEvent) => {
      if (!mountedRef.current) return
      // Don't reconnect on clean close (code 1000) or if job is done
      if (event.code === 1000) return

      // Exponential backoff reconnect
      const delay = backoffRef.current
      backoffRef.current = Math.min(delay * 2, MAX_BACKOFF_MS)

      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current) connect()
      }, delay)
    }
  }, [jobId])

  useEffect(() => {
    mountedRef.current = true

    if (jobId) {
      connect()
    }

    return () => {
      mountedRef.current = false
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'component unmounted')
        wsRef.current = null
      }
    }
  }, [jobId, connect])

  return state
}
