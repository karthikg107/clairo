'use client'

/**
 * CLR-042 — Shown when a share link is expired, revoked, or unknown.
 *
 * All three states render this SAME view — the backend already returns
 * identical 404s for them (CLR-041 anti-enumeration), and the copy here
 * deliberately doesn't distinguish "expired" from "revoked" either.
 */

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { FileQuestion } from 'lucide-react'

export function SharedLinkUnavailable() {
  const t = useTranslations('sharedPage.unavailable')

  return (
    <main className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="flex flex-col items-center text-center max-w-sm">
        <div className="w-14 h-14 rounded-full bg-brand-50 flex items-center justify-center mb-4">
          <FileQuestion className="w-6 h-6 text-brand-700" aria-hidden />
        </div>
        <h1 className="text-lg font-bold text-neutral-900">{t('heading')}</h1>
        <p className="text-sm text-neutral-500 mt-2 mb-6 leading-relaxed">{t('body')}</p>
        <Link
          href="/upload"
          className="
            px-5 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
            flex items-center
            hover:bg-brand-800 transition-colors
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
          "
        >
          {t('cta')}
        </Link>
      </div>
    </main>
  )
}
