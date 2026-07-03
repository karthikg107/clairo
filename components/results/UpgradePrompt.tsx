'use client'

/**
 * CLR-018 — Sticky upgrade prompt.
 *
 * Shown only after the reader has scrolled past 2+ clause cards (engaged
 * reading signal), not on first paint — see AnalysisResultsScreen's
 * IntersectionObserver-based `seenClauseCount` tracking.
 */

import { useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { X, Sparkles } from 'lucide-react'
import { track } from '@/lib/analytics'

interface UpgradePromptProps {
  onUpgrade: () => void
  onDismiss: () => void
}

export function UpgradePrompt({ onUpgrade, onDismiss }: UpgradePromptProps) {
  const t = useTranslations('results.upgrade')

  // CLR-045 — the upgrade prompt became visible to an engaged reader.
  useEffect(() => {
    track('upgrade_prompted')
  }, [])

  return (
    <div
      role="complementary"
      aria-label={t('aria_label')}
      className="
        sticky bottom-0 z-30
        bg-brand-700 text-white
        px-4 py-3
        flex items-center gap-3
        shadow-[0_-4px_12px_rgba(0,0,0,0.1)]
      "
    >
      <Sparkles className="w-5 h-5 shrink-0 text-accent-300" aria-hidden />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium leading-snug">{t('message')}</p>
      </div>
      <button
        type="button"
        onClick={onUpgrade}
        className="
          shrink-0 px-3 py-1.5 rounded-xl bg-white text-brand-800 text-xs font-semibold
          hover:bg-brand-50 transition-colors
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white
        "
      >
        {t('cta')}
      </button>
      <button
        type="button"
        onClick={onDismiss}
        aria-label={t('dismiss')}
        className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
      >
        <X className="w-4 h-4" aria-hidden />
      </button>
    </div>
  )
}
