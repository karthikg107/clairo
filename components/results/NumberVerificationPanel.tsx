'use client'

/**
 * CLR-040 — OCR number verification warning.
 *
 * Every number in analysis output is tappable.
 * Tapping opens this panel showing:
 *   - The number value
 *   - The context sentence from original_text (OCR source)
 *   - A warning that OCR may mis-read numbers
 *
 * This screen is NON-NEGOTIABLE — cannot be skipped or disabled.
 * Legal requirement: users must be able to verify every number
 * against the source document before making any decision.
 */

import { useTranslations } from 'next-intl'
import { X, AlertTriangle, FileText } from 'lucide-react'
import { useEffect, useRef, useCallback } from 'react'

export interface VerifiableNumber {
  value: string // e.g. "$1,000" or "12 months"
  context: string // sentence containing the number from original_text
}

interface NumberVerificationPanelProps {
  number: VerifiableNumber
  clauseTitle: string
  onClose: () => void
}

export function NumberVerificationPanel({
  number,
  clauseTitle,
  onClose,
}: NumberVerificationPanelProps) {
  const t = useTranslations('number_verification')
  const closeBtnRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // Focus close button on mount; restore focus to trigger on close
  useEffect(() => {
    closeBtnRef.current?.focus()
  }, [])

  // Escape-to-close + focus trap at document level — avoids key listeners
  // on non-interactive elements (jsx-a11y), same pattern as
  // DeleteAccountDialog / ShareSheet.
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key !== 'Tab' || !panelRef.current) return
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (
        e.shiftKey ? document.activeElement === first : document.activeElement === last
      ) {
        e.preventDefault()
        ;(e.shiftKey ? last : first).focus()
      }
    },
    [onClose]
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // Highlight the number value within the context string
  const highlightedContext = highlightNumber(number.context, number.value)

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center px-0 sm:px-4">
      {/* Backdrop — a real button so closing works via keyboard too */}
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 cursor-default"
      />
      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="nvp-heading"
        className="
          relative w-full sm:max-w-sm bg-white rounded-t-3xl sm:rounded-2xl
          shadow-xl flex flex-col
          max-h-[85vh] overflow-y-auto
        "
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 id="nvp-heading" className="text-base font-semibold text-neutral-900">
            {t('heading')}
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label={t('close')}
            className="
              w-8 h-8 rounded-full flex items-center justify-center
              text-neutral-500 hover:bg-neutral-100 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
            "
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>

        {/* Number value chip */}
        <div className="px-5 pb-4">
          <div className="inline-flex items-center gap-2 bg-brand-50 rounded-xl px-3 py-1.5">
            <span className="text-lg font-bold text-brand-800">{number.value}</span>
          </div>
          <p className="text-xs text-neutral-500 mt-1">
            {t('in_clause', { clause: clauseTitle })}
          </p>
        </div>

        <hr className="border-neutral-100 mx-5" />

        {/* Source text section */}
        <div className="px-5 py-4">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="w-4 h-4 text-neutral-400" aria-hidden />
            <span className="text-xs font-medium text-neutral-500 uppercase tracking-wide">
              {t('source_label')}
            </span>
          </div>
          <p
            className="text-sm text-neutral-700 leading-relaxed font-mono bg-neutral-50 rounded-xl p-3"
            aria-label={t('source_aria')}
            dangerouslySetInnerHTML={{ __html: highlightedContext }}
          />
        </div>

        {/* OCR warning — non-dismissable */}
        <div className="mx-5 mb-5 rounded-xl bg-warning-50 border border-warning-200 px-4 py-3 flex gap-3">
          <AlertTriangle
            className="w-4 h-4 text-warning-600 shrink-0 mt-0.5"
            aria-hidden
          />
          <div>
            <p className="text-sm font-medium text-warning-800 mb-0.5">
              {t('warning_heading')}
            </p>
            <p className="text-xs text-warning-700 leading-relaxed">
              {t('warning_body')}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Wraps the first occurrence of `value` in the context string with
 * a highlighted <mark> span. Sanitizes content (no raw HTML from Claude).
 */
function highlightNumber(context: string, value: string): string {
  // Escape HTML entities in both strings first
  const safeContext = escapeHtml(context)
  const safeValue = escapeHtml(value)

  const idx = safeContext.indexOf(safeValue)
  if (idx === -1) return safeContext

  return (
    safeContext.slice(0, idx) +
    `<mark class="bg-warning-200 text-warning-900 rounded px-0.5 not-italic">${safeValue}</mark>` +
    safeContext.slice(idx + safeValue.length)
  )
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

/**
 * Inline tappable number chip — renders inside clause explanation text.
 * Each instance of a number in explanation text should be wrapped with this.
 */
interface TappableNumberProps {
  number: VerifiableNumber
  onTap: (number: VerifiableNumber) => void
}

export function TappableNumber({ number, onTap }: TappableNumberProps) {
  const t = useTranslations('number_verification')
  return (
    <button
      type="button"
      onClick={() => onTap(number)}
      aria-label={t('tap_aria', { value: number.value })}
      className="
        inline-flex items-center gap-0.5
        font-semibold text-brand-700 underline underline-offset-2
        hover:text-brand-800
        focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500 focus-visible:rounded
        cursor-pointer
      "
    >
      {number.value}
      <AlertTriangle className="w-3 h-3 text-warning-500 shrink-0" aria-hidden />
    </button>
  )
}
