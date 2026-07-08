'use client'

/**
 * CLR-036 — Non-dismissable legal disclaimer.
 *
 * Requirements (non-negotiable):
 * - Sticky above every result — NEVER hidden or dismissable
 * - danger-100 background (#FEF2F2), danger-700 left border (3px)
 * - Translated into the user's output language
 * - No close button, no toggle, no "don't show again"
 * - Cannot be A/B tested away
 *
 * Usage: render above every AnalysisResult, every time, unconditionally.
 */

import { useTranslations } from 'next-intl'
import { AlertTriangle } from 'lucide-react'

/**
 * @param sticky When true (default) the disclaimer pins itself to the top of
 *   the scroll container. Pass false when a parent already provides the sticky
 *   positioning — e.g. the results screen stacks it under a sticky header in a
 *   single sticky wrapper, so a second `sticky top-0` here would fight it and
 *   misalign (the old bug: header + a `top-[57px]` hardcoded offset).
 */
export function LegalDisclaimer({ sticky = true }: { sticky?: boolean }) {
  const t = useTranslations('disclaimer')

  return (
    /*
     * role="note" — landmark that screen readers can navigate to.
     * Not role="alert" because this is persistent, not a transient announcement.
     * aria-label distinguishes it from other content on the page.
     */
    <aside
      role="note"
      aria-label={t('aria_label')}
      // Non-dismissable: no state, no close handler, always rendered
      className={`
        ${sticky ? 'sticky top-0 z-40' : ''}
        bg-danger-50 border-l-[3px] border-danger-700
        px-4 py-3
        w-full
      `}
      style={{
        // Inline fallbacks for environments where Tailwind custom colors aren't loaded
        backgroundColor: '#FEF2F2',
        borderLeftColor: '#B91C1C',
      }}
    >
      <div className="flex gap-3 items-start max-w-2xl mx-auto">
        {/* Warning icon — aria-hidden, meaning is in text */}
        <AlertTriangle
          className="w-4 h-4 text-danger-700 shrink-0 mt-0.5"
          aria-hidden="true"
          style={{ color: '#B91C1C' }}
        />

        <p className="text-sm text-danger-900 leading-snug" style={{ color: '#7F1D1D' }}>
          <strong className="font-semibold">{t('heading')}</strong> {t('body')}
        </p>
      </div>
    </aside>
  )
}

/**
 * Wrapper that guarantees the disclaimer is always above analysis output.
 * Use this instead of <LegalDisclaimer /> directly to make the coupling explicit.
 */
export function AnalysisWithDisclaimer({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      {/* Disclaimer is ALWAYS first — never conditionally rendered */}
      <LegalDisclaimer />
      <div className="flex-1">{children}</div>
    </div>
  )
}
