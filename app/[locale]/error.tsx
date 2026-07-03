'use client'

/**
 * CLR-047 — localized error page (unexpected server/render failures).
 *
 * Apologizes, confirms the user's document was NOT stored (documents
 * are processed in memory and never persisted — an error changes
 * nothing about that), and offers home / try-again. Deliberately shows
 * NO technical details: `error` is received per Next's contract but
 * never rendered.
 */

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { AlertTriangle } from 'lucide-react'

export default function ErrorPage({
  error: _error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  const t = useTranslations('errorPages.server_error')

  return (
    <main className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="flex flex-col items-center text-center max-w-sm">
        <div className="w-14 h-14 rounded-full bg-warning-50 flex items-center justify-center mb-4">
          <AlertTriangle className="w-6 h-6 text-warning-700" aria-hidden />
        </div>
        <h1 className="text-lg font-bold text-neutral-900">{t('heading')}</h1>
        <p className="text-sm text-neutral-500 mt-2 leading-relaxed">{t('body')}</p>
        <p className="text-sm font-medium text-neutral-700 mt-3 mb-6 leading-relaxed">
          {t('not_stored')}
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <button
            type="button"
            onClick={reset}
            className="
              px-5 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
              flex items-center justify-center
              hover:bg-brand-800 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
            "
          >
            {t('retry_cta')}
          </button>
          <Link
            href="/"
            className="
              px-5 h-11 rounded-2xl border border-neutral-200 text-neutral-700 text-sm font-medium
              flex items-center justify-center
              hover:bg-neutral-50 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
            "
          >
            {t('home_cta')}
          </Link>
        </div>
      </div>
    </main>
  )
}
