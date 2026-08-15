/**
 * CrewSelector.tsx — Crew selection radio cards
 * ===============================================
 * Renders three styled radio cards, one per available crew.
 * The selected card is highlighted with the HA blue accent colour.
 */

import type { FC } from 'react'

export type CrewId = 'code_review' | 'ha_automation' | 'ha_assistant'

interface CrewOption {
  id: CrewId
  label: string
  description: string
  icon: string
}

const CREWS: CrewOption[] = [
  {
    id: 'code_review',
    label: 'Code Review',
    description: 'Developer writes code → Reviewer critiques → DevOps commits to GitHub',
    icon: '🧑‍💻',
  },
  {
    id: 'ha_automation',
    label: 'HA Automation',
    description: 'Natural language → HA automation YAML → GitHub commit',
    icon: '🏠',
  },
  {
    id: 'ha_assistant',
    label: 'HA Assistant',
    description: 'Survey sensors → suggest automations → commit top pick',
    icon: '🤖',
  },
]

interface CrewSelectorProps {
  value: CrewId
  onChange: (crew: CrewId) => void
  disabled?: boolean
}

export const CrewSelector: FC<CrewSelectorProps> = ({ value, onChange, disabled = false }) => {
  return (
    <div className="flex flex-col gap-2" role="radiogroup" aria-label="Select crew">
      {CREWS.map(crew => {
        const isSelected = crew.id === value
        return (
          <button
            key={crew.id}
            type="button"
            role="radio"
            aria-checked={isSelected}
            disabled={disabled}
            onClick={() => onChange(crew.id)}
            className={[
              'w-full text-left rounded-lg border px-4 py-3 transition-all duration-150',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue',
              disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-ha-blue/60',
              isSelected
                ? 'border-ha-blue bg-ha-blue/10'
                : 'border-ha-border bg-ha-bg hover:bg-ha-surface',
            ].join(' ')}
          >
            <div className="flex items-center gap-3">
              <span className="text-xl" aria-hidden="true">{crew.icon}</span>
              <div className="flex-1 min-w-0">
                <div className={`text-sm font-semibold ${isSelected ? 'text-ha-blue' : 'text-ha-text'}`}>
                  {crew.label}
                </div>
                <div className="text-xs text-ha-muted mt-0.5 leading-snug">
                  {crew.description}
                </div>
              </div>
              {/* Radio indicator */}
              <div
                className={[
                  'w-4 h-4 rounded-full border-2 flex-shrink-0 transition-colors',
                  isSelected ? 'border-ha-blue bg-ha-blue' : 'border-ha-border',
                ].join(' ')}
                aria-hidden="true"
              />
            </div>
          </button>
        )
      })}
    </div>
  )
}
