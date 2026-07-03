'use client'

/**
 * CLR-045 — cookie/analytics consent banner.
 *
 * Analytics starts ONLY after "Accept" — declining (or never answering)
 * means PostHog is never initialized. Both choices are equally prominent
 * (no dark patterns: decline is not hidden, shrunken, or grayed out).
 */

import { useTranslations } from 'next-intl'

interface ConsentBannerProps {
  onAccept: () => void
  onDecline: () => void
}

export function ConsentBanner({ onAccept, onDecline }: ConsentBannerProps) {
  const t = useTranslations('consentBanner')

  return (
    <div
      role="region"
      aria-label={t('aria_label')}
      className="fixed bottom-0 inset-x-0 z-50 bg-white border-t border-neutral-200 px-4 py-4 shadow-[0_-4px_16px_rgba(0,0,0,0.06)]"
    >
      <div className="max-w-2xl mx-auto flex flex-col sm:flex-row sm:items-center gap-3">
        <p className="flex-1 text-xs text-neutral-600 leading-relaxed">{t('body')}</p>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={onDecline}
            className="
              px-4 h-10 rounded-2xl border border-neutral-200 text-sm font-medium text-neutral-700
              hover:bg-neutral-50 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
            "
          >
            {t('decline')}
          </button>
          <button
            type="button"
            onClick={onAccept}
            className="
              px-4 h-10 rounded-2xl bg-brand-700 text-white text-sm font-semibold
              hover:bg-brand-800 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
            "
          >
            {t('accept')}
          </button>
        </div>
      </div>
    </div>
  )
}
