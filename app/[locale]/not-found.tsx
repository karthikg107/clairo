/**
 * CLR-047 — localized 404 page.
 *
 * Rendered for any unknown path inside the locale segment (see the
 * [...rest] catch-all that calls notFound()). Friendly message, link
 * home, and an upload CTA — no technical details.
 */
import Link from 'next/link'
import { getTranslations } from 'next-intl/server'
import { FileQuestion } from 'lucide-react'

export default async function NotFound() {
  const t = await getTranslations('errorPages.not_found')

  return (
    <main className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="flex flex-col items-center text-center max-w-sm">
        <div className="w-14 h-14 rounded-full bg-brand-50 flex items-center justify-center mb-4">
          <FileQuestion className="w-6 h-6 text-brand-700" aria-hidden />
        </div>
        <h1 className="text-lg font-bold text-neutral-900">{t('heading')}</h1>
        <p className="text-sm text-neutral-500 mt-2 mb-6 leading-relaxed">{t('body')}</p>
        <div className="flex flex-col sm:flex-row gap-2">
          <Link
            href="/upload"
            className="
              px-5 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
              flex items-center justify-center
              hover:bg-brand-800 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
            "
          >
            {t('upload_cta')}
          </Link>
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
