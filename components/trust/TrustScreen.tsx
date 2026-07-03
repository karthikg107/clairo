'use client'

/**
 * CLR-022 — Trust screen & TOS acceptance (SCR-02)
 *
 * HARD BLOCKER: This screen is non-negotiable and cannot be skipped,
 * A/B tested away, or shown only once without database confirmation.
 * Legal advisor approval required before any copy changes.
 *
 * Shows on first use (and whenever TOS version changes).
 * Blocks all app functionality until accepted.
 */
import { useState, useEffect, useCallback, useId } from 'react'
import { useTranslations } from 'next-intl'
import { ShieldCheck, Lock, Trash2, Scale } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''
const CURRENT_TOS_VERSION = '1.0'

// Trust statement config — icons + i18n keys
const TRUST_STATEMENTS = [
  { key: 'privacy', Icon: Lock },
  { key: 'deletion', Icon: Trash2 },
  { key: 'explain', Icon: Scale },
] as const

interface TrustScreenProps {
  /** Called after confirmed DB acceptance. Parent should hide screen. */
  onAccepted: () => void
  /** Injected token for test/Storybook usage */
  _tokenOverride?: string
}

export function TrustScreen({ onAccepted, _tokenOverride }: TrustScreenProps) {
  const t = useTranslations('trust')
  const checkboxId = useId()

  const [checked, setChecked] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Trap focus inside this overlay
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    return () => {
      prev?.focus()
    }
  }, [])

  const handleAccept = useCallback(async () => {
    if (!checked || submitting) return
    setSubmitting(true)
    setError(null)

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (_tokenOverride) {
        headers['Authorization'] = `Bearer ${_tokenOverride}`
      }

      const res = await fetch(`${API_BASE}/api/v1/consent`, {
        method: 'POST',
        credentials: 'include',
        headers,
        body: JSON.stringify({ tos_version: CURRENT_TOS_VERSION }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail ?? t('error_generic'))
      }

      onAccepted()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('error_generic'))
      setSubmitting(false)
    }
  }, [checked, submitting, onAccepted, t, _tokenOverride])

  return (
    // Full-screen overlay — fixed, covers everything, z-50
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="trust-heading"
      className="fixed inset-0 z-50 flex flex-col bg-white overflow-y-auto"
    >
      <div className="flex flex-col min-h-full px-5 py-8 max-w-md mx-auto w-full">
        {/* Brand + shield */}
        <div className="flex flex-col items-center mb-8 mt-4">
          <div className="w-14 h-14 rounded-full bg-brand-50 flex items-center justify-center mb-4">
            <ShieldCheck className="w-7 h-7 text-brand-700" aria-hidden />
          </div>
          <h1
            id="trust-heading"
            className="text-xl font-semibold text-neutral-900 text-center"
          >
            {t('heading')}
          </h1>
          <p className="mt-2 text-sm text-neutral-500 text-center leading-relaxed">
            {t('subheading')}
          </p>
        </div>

        {/* Three trust statements */}
        <div className="flex flex-col gap-4 mb-8">
          {TRUST_STATEMENTS.map(({ key, Icon }) => (
            <div
              key={key}
              className="flex gap-4 rounded-2xl border border-neutral-100 bg-neutral-50 p-4"
            >
              <div className="shrink-0 w-9 h-9 rounded-xl bg-white border border-neutral-200 flex items-center justify-center mt-0.5">
                <Icon className="w-4 h-4 text-brand-700" aria-hidden />
              </div>
              <div>
                <p className="text-sm font-semibold text-neutral-900 mb-0.5">
                  {t(`statements.${key}.title`)}
                </p>
                <p className="text-sm text-neutral-600 leading-relaxed">
                  {t(`statements.${key}.body`)}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Spacer pushes checkbox + button to bottom on short screens */}
        <div className="flex-1" />

        {/* Checkbox + label */}
        <label
          htmlFor={checkboxId}
          className="flex items-start gap-3 mb-5 cursor-pointer"
        >
          <input
            id={checkboxId}
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="mt-0.5 h-5 w-5 rounded border-neutral-300 text-brand-700 focus:ring-brand-500"
            aria-describedby="trust-links"
          />
          <span className="text-sm text-neutral-700 leading-relaxed">
            {t.rich('checkbox_label', {
              terms: (chunks) => (
                <a
                  href="/terms"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-700 underline hover:text-brand-800"
                >
                  {chunks}
                </a>
              ),
              privacy: (chunks) => (
                <a
                  href="/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-700 underline hover:text-brand-800"
                >
                  {chunks}
                </a>
              ),
            })}
          </span>
        </label>

        <p id="trust-links" className="sr-only">
          {t('links_hint')}
        </p>

        {/* Error message */}
        {error && (
          <p role="alert" className="text-sm text-danger-600 mb-3">
            {error}
          </p>
        )}

        {/* Accept button */}
        <button
          type="button"
          onClick={handleAccept}
          disabled={!checked || submitting}
          aria-disabled={!checked || submitting}
          className="
            w-full h-12 rounded-2xl text-sm font-semibold text-white
            bg-brand-700 hover:bg-brand-800
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
          "
        >
          {submitting ? t('button_loading') : t('button_accept')}
        </button>

        {/* Legal disclaimer — non-dismissable */}
        <p className="mt-4 text-xs text-neutral-500 text-center leading-relaxed">
          {t('legal_note')}
        </p>
      </div>
    </div>
  )
}
