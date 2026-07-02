'use client'

/**
 * CLR-018/CLR-037 — "Find a professional" card shown at the bottom of the
 * results screen.
 *
 * Resolves a country + document-type specific referral (tenants' union,
 * employment tribunal, bar association, legal aid body) via
 * lib/referrals.ts. Falls back to a translated generic CTA if no referral
 * is found for the given country.
 */

import { useTranslations } from 'next-intl'
import { Scale, ExternalLink } from 'lucide-react'
import { getProfessionalReferral } from '@/lib/referrals'

interface FindProfessionalCardProps {
  country: string
  documentType: string
}

export function FindProfessionalCard({
  country,
  documentType,
}: FindProfessionalCardProps) {
  const t = useTranslations('results.professional')
  const referral = getProfessionalReferral(country, documentType)

  return (
    <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-5 text-start">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-brand-50 flex items-center justify-center shrink-0">
          <Scale className="w-5 h-5 text-brand-700" aria-hidden />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-neutral-900">{t('heading')}</h3>
          <p className="text-sm text-neutral-600 mt-1 leading-relaxed">{t('body')}</p>

          {referral && (
            <>
              <p className="text-xs text-neutral-500 uppercase tracking-wide mt-3 mb-1 font-medium">
                {t('referral_label')}
              </p>
              <p className="text-sm font-semibold text-neutral-900 mb-1">
                {referral.org}
              </p>
              <a
                href={referral.url}
                target="_blank"
                rel="noopener noreferrer"
                className="
                  inline-flex items-center gap-1.5
                  text-sm font-medium text-brand-700 hover:text-brand-800
                  underline underline-offset-2
                "
                aria-label={t('link_aria', { org: referral.org })}
              >
                {t('link_text', { org: referral.org })}
                <ExternalLink className="w-3.5 h-3.5" aria-hidden />
              </a>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
