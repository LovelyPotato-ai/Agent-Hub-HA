/**
 * PromptInput.tsx — Prompt textarea with crew-specific options
 * =============================================================
 * Renders a textarea for the user's prompt, optional entity list inputs
 * for HA crews, a character counter, and a submit button.
 */

import { useState, type FC, type FormEvent } from 'react'
import type { CrewId } from './CrewSelector'

interface PromptInputProps {
  crew: CrewId
  onSubmit: (crew: CrewId, prompt: string, options: Record<string, unknown>) => void
  disabled?: boolean
}

const PLACEHOLDERS: Record<CrewId, string> = {
  code_review:
    'e.g. Write a Python utility that validates Home Assistant entity IDs and returns their domain and object_id parts.',
  ha_automation:
    'e.g. Turn off all lights and set the thermostat to 18°C when everyone leaves home.',
  ha_assistant:
    'e.g. Analyse the current sensor states and suggest energy-saving automations for the living room.',
}

const MAX_PROMPT_LENGTH = 2000

export const PromptInput: FC<PromptInputProps> = ({ crew, onSubmit, disabled = false }) => {
  const [prompt, setPrompt] = useState('')
  const [entities, setEntities] = useState('')

  const needsEntities = crew === 'ha_automation' || crew === 'ha_assistant'
  const entityLabel = crew === 'ha_automation' ? 'Entities to read (optional)' : 'Entities to survey (optional)'
  const entityKey = crew === 'ha_automation' ? 'entities_to_read' : 'entities_to_survey'
  const entityPlaceholder = 'sensor.living_room_temperature, binary_sensor.motion_hallway'

  const charCount = prompt.length
  const isOverLimit = charCount > MAX_PROMPT_LENGTH
  const canSubmit = prompt.trim().length > 0 && !isOverLimit && !disabled

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit) return

    const options: Record<string, unknown> = {}
    if (needsEntities && entities.trim()) {
      options[entityKey] = entities
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)
    }

    onSubmit(crew, prompt.trim(), options)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      {/* Prompt textarea */}
      <div className="relative">
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder={PLACEHOLDERS[crew]}
          disabled={disabled}
          rows={6}
          maxLength={MAX_PROMPT_LENGTH + 100}
          className={[
            'w-full rounded-lg border bg-ha-bg px-3 py-2.5 text-sm text-ha-text',
            'placeholder:text-ha-muted resize-none',
            'focus:outline-none focus:ring-2 focus:ring-ha-blue',
            'transition-colors duration-150',
            disabled ? 'opacity-50 cursor-not-allowed' : '',
            isOverLimit ? 'border-red-500' : 'border-ha-border',
          ].join(' ')}
          aria-label="Prompt"
        />
        {/* Character counter */}
        <span
          className={[
            'absolute bottom-2 right-3 text-xs',
            isOverLimit ? 'text-red-400' : 'text-ha-muted',
          ].join(' ')}
        >
          {charCount}/{MAX_PROMPT_LENGTH}
        </span>
      </div>

      {/* Entity list input (HA crews only) */}
      {needsEntities && (
        <div>
          <label className="block text-xs text-ha-muted mb-1.5">{entityLabel}</label>
          <input
            type="text"
            value={entities}
            onChange={e => setEntities(e.target.value)}
            placeholder={entityPlaceholder}
            disabled={disabled}
            className={[
              'w-full rounded-lg border border-ha-border bg-ha-bg px-3 py-2 text-sm text-ha-text',
              'placeholder:text-ha-muted',
              'focus:outline-none focus:ring-2 focus:ring-ha-blue',
              disabled ? 'opacity-50 cursor-not-allowed' : '',
            ].join(' ')}
            aria-label={entityLabel}
          />
          <p className="mt-1 text-xs text-ha-muted">
            Comma-separated entity IDs. Leave empty to skip sensor reading.
          </p>
        </div>
      )}

      {/* Submit button */}
      <button
        type="submit"
        disabled={!canSubmit}
        className={[
          'w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-all duration-150',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-ha-blue',
          canSubmit
            ? 'bg-ha-blue hover:bg-ha-blue-dark text-white cursor-pointer'
            : 'bg-ha-border text-ha-muted cursor-not-allowed',
        ].join(' ')}
      >
        {disabled ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Running…
          </span>
        ) : (
          'Run Crew'
        )}
      </button>
    </form>
  )
}
