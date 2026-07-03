'use client'

/**
 * CLR-048 — PWA install banner (shown after 3+ visits when the browser
 * offers installation). Dismissable permanently — no nagging.
 */

import { useTranslations } from 'next-intl'
import { Download, X } from 'lucide-react'

interface InstallPromptProps {
  onInstall: () => void
  onDismiss: () => void
}

export function InstallPrompt({ onInstall, onDismiss }: InstallPromptProps) {
  const t = useTranslations('pwa.install')

  return (
    <div
      role="region"
      aria-label={t('aria_label')}
      className="fixed bottom-4 inset-x-4 z-40 mx-auto max-w-md rounded-2xl border border-neutral-200 bg-white p-4 shadow-lg"
    >
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50">
          <Download className="h-5 w-5 text-brand-700" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-neutral-900">{t('heading')}</p>
          <p className="text-xs text-neutral-500">{t('body')}</p>
        </div>
        <button
          type="button"
          onClick={onInstall}
          className="
            shrink-0 px-3 h-9 rounded-xl bg-brand-700 text-white text-xs font-semibold
            hover:bg-brand-800 transition-colors
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
          "
        >
          {t('cta')}
        </button>
        <button
          type="button"
          onClick={onDismiss}
          aria-label={t('dismiss')}
          className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-neutral-400 hover:bg-neutral-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          <X className="w-4 h-4" aria-hidden />
        </button>
      </div>
    </div>
  )
}
