'use client'

/**
 * CLR-038 — Prohibited document blocking screen.
 *
 * Shown when /api/v1/classify returns is_prohibited=true.
 * Full block — no partial analysis, no bypass.
 * Shows type-specific referral to an appropriate free resource.
 *
 * SECURITY:
 * - No analysis is ever performed on prohibited document types (enforced in backend)
 * - Quota is NOT decremented for prohibited documents (backend enforces this too)
 * - This screen provides the referral; the backend provides the type-specific reason
 */

import { useTranslations } from 'next-intl'
import { ShieldOff, ExternalLink, RotateCcw } from 'lucide-react'

/** Matches the referral object from /api/v1/classify */
export interface ProhibitedReferral {
  org: string
  url: string
  reason_key: string
}

interface ProhibitedDocumentScreenProps {
  documentType: string
  referral: ProhibitedReferral | null
  /** Called when user taps "Upload a different document" */
  onReset: () => void
}

export function ProhibitedDocumentScreen({
  documentType,
  referral,
  onReset,
}: ProhibitedDocumentScreenProps) {
  const t = useTranslations('prohibited')

  const reasonKey = referral?.reason_key ?? 'default'

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex flex-col items-center px-5 py-10 min-h-[60vh] max-w-md mx-auto text-center"
    >
      {/* Icon */}
      <div className="w-16 h-16 rounded-full bg-danger-50 flex items-center justify-center mb-6">
        <ShieldOff className="w-8 h-8 text-danger-600" aria-hidden />
      </div>

      {/* Heading */}
      <h1 className="text-xl font-semibold text-neutral-900 mb-3">
        {t('heading')}
      </h1>

      {/* Reason */}
      <p className="text-sm text-neutral-600 leading-relaxed mb-6">
        {t(`reasons.${reasonKey}`, { fallback: t('reasons.default') })}
      </p>

      {/* Referral card — always shown if referral provided */}
      {referral && (
        <div className="w-full rounded-2xl border border-neutral-200 bg-neutral-50 p-4 mb-6 text-start">
          <p className="text-xs text-neutral-500 uppercase tracking-wide mb-1 font-medium">
            {t('referral_label')}
          </p>
          <p className="text-sm font-semibold text-neutral-900 mb-2">
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
            aria-label={t('referral_link_aria', { org: referral.org })}
          >
            {t('referral_link_text')}
            <ExternalLink className="w-3.5 h-3.5" aria-hidden />
          </a>
        </div>
      )}

      {/* No-partial-analysis notice */}
      <p className="text-xs text-neutral-400 mb-8 leading-relaxed">
        {t('no_partial_analysis')}
      </p>

      {/* Reset button */}
      <button
        type="button"
        onClick={onReset}
        className="
          flex items-center gap-2
          w-full h-12 justify-center
          rounded-2xl border border-neutral-200
          text-sm font-medium text-neutral-700
          hover:bg-neutral-50 transition-colors
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
        "
      >
        <RotateCcw className="w-4 h-4" aria-hidden />
        {t('upload_different')}
      </button>
    </div>
  )
}
