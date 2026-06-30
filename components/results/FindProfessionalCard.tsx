'use client'

/**
 * CLR-018 — "Find a professional" card shown at the bottom of the results screen.
 *
 * Scope note: country-specific referral directory lookup is CLR-037. This card
 * is the generic CTA slot for CLR-018; it accepts an optional pre-resolved
 * `href` and falls back to a translated generic message when none is supplied.
 */

import { useTranslations } from 'next-intl'
import { Scale, ExternalLink } from 'lucide-react'

interface FindProfessionalCardProps {
  href?: string
}

export function FindProfessionalCard({ href }: FindProfessionalCardProps) {
  const t = useTranslations('results.professional')

  return (
    <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-5 text-start">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-brand-50 flex items-center justify-center shrink-0">
          <Scale className="w-5 h-5 text-brand-700" aria-hidden />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-neutral-900">{t('heading')}</h3>
          <p className="text-sm text-neutral-600 mt-1 leading-relaxed">{t('body')}</p>
          <a
            href={href ?? '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="
              mt-3 inline-flex items-center gap-1.5
              text-sm font-medium text-brand-700 hover:text-brand-800
              underline underline-offset-2
            "
          >
            {t('cta')}
            <ExternalLink className="w-3.5 h-3.5" aria-hidden />
          </a>
        </div>
      </div>
    </div>
  )
}
