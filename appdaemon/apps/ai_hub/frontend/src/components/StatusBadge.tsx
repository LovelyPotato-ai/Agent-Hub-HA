/**
 * StatusBadge.tsx — Animated status pill
 * ========================================
 * Displays the current hub status as a colour-coded animated badge.
 * Status values: idle | running | done | error
 */

import type { FC } from 'react'
import type { HubStatus } from '../api/aiHubClient'

interface StatusBadgeProps {
  status: HubStatus
}

const STATUS_CONFIG: Record<HubStatus, { label: string; dot: string; text: string; bg: string; animate: boolean }> = {
  idle: {
    label: 'Idle',
    dot: 'bg-ha-muted',
    text: 'text-ha-muted',
    bg: 'bg-ha-border/30',
    animate: false,
  },
  running: {
    label: 'Running',
    dot: 'bg-yellow-400',
    text: 'text-yellow-400',
    bg: 'bg-yellow-400/10',
    animate: true,
  },
  done: {
    label: 'Done',
    dot: 'bg-green-400',
    text: 'text-green-400',
    bg: 'bg-green-400/10',
    animate: false,
  },
  error: {
    label: 'Error',
    dot: 'bg-red-400',
    text: 'text-red-400',
    bg: 'bg-red-400/10',
    animate: false,
  },
}

export const StatusBadge: FC<StatusBadgeProps> = ({ status }) => {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.idle

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${cfg.bg} ${cfg.text}`}
      role="status"
      aria-label={`Status: ${cfg.label}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dot} ${cfg.animate ? 'animate-pulse-slow' : ''}`}
        aria-hidden="true"
      />
      {cfg.label}
    </span>
  )
}
