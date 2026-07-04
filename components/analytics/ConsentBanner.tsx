'use client'

/**
 * CLR-045/CLR-055 — cookie/analytics consent banner with granular options.
 *
 * Two views:
 *  - Compact: Accept / Decline / Customize — equal prominence, no dark
 *    patterns (decline is never hidden, shrunken, or grayed out).
 *  - Granular (Customize): per-category toggles. Essential is always on
 *    (and honestly labeled as such); Analytics is the only optional
 *    category Clairo has. "Save choices" applies exactly what's toggled.
 *
 * Analytics starts ONLY after explicit opt-in — declining (or never
 * answering) means PostHog is never even downloaded (see lib/analytics).
 */

import { useState, useId } from 'react'
import { useTranslations } from 'next-intl'

interface ConsentBannerProps {
  onAccept: () => void
  onDecline: () => void
}

export function ConsentBanner({ onAccept, onDecline }: ConsentBannerProps) {
  const t = useTranslations('consentBanner')
  const [customizing, setCustomizing] = useState(false)
  const [analyticsChecked, setAnalyticsChecked] = useState(false)
  const analyticsId = useId()
  const essentialId = useId()

  const handleSave = () => {
    if (analyticsChecked) onAccept()
    else onDecline()
  }

  return (
    <div
      role="region"
      aria-label={t('aria_label')}
      className="fixed bottom-0 inset-x-0 z-50 bg-white border-t border-neutral-200 px-4 py-4 shadow-[0_-4px_16px_rgba(0,0,0,0.06)]"
    >
      <div className="max-w-2xl mx-auto flex flex-col gap-3">
        <p className="text-xs text-neutral-600 leading-relaxed">{t('body')}</p>

        {customizing && (
          <div className="flex flex-col gap-2 rounded-2xl border border-neutral-200 p-3">
            {/* Essential — always on */}
            <div className="flex items-start justify-between gap-3">
              <label htmlFor={essentialId} className="min-w-0">
                <span className="block text-xs font-semibold text-neutral-900">
                  {t('categories.essential.name')}
                </span>
                <span className="block text-[11px] text-neutral-500 leading-relaxed">
                  {t('categories.essential.description')}
                </span>
              </label>
              <input
                id={essentialId}
                type="checkbox"
                checked
                disabled
                aria-label={t('categories.essential.name')}
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-neutral-300 text-brand-700"
              />
            </div>
            {/* Analytics — the only optional category */}
            <div className="flex items-start justify-between gap-3 border-t border-neutral-100 pt-2">
              <label htmlFor={analyticsId} className="min-w-0">
                <span className="block text-xs font-semibold text-neutral-900">
                  {t('categories.analytics.name')}
                </span>
                <span className="block text-[11px] text-neutral-500 leading-relaxed">
                  {t('categories.analytics.description')}
                </span>
              </label>
              <input
                id={analyticsId}
                type="checkbox"
                checked={analyticsChecked}
                onChange={(e) => setAnalyticsChecked(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-neutral-300 text-brand-700 focus-visible:ring-2 focus-visible:ring-brand-500"
              />
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {customizing ? (
            <button
              type="button"
              onClick={handleSave}
              className="
                px-4 h-10 rounded-2xl bg-brand-700 text-white text-sm font-semibold
                hover:bg-brand-800 transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
              "
            >
              {t('save')}
            </button>
          ) : (
            <>
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
                onClick={() => setCustomizing(true)}
                className="
                  px-4 h-10 rounded-2xl text-sm font-medium text-brand-700
                  hover:bg-brand-50 transition-colors
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
                "
              >
                {t('customize')}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
