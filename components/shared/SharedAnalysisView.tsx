'use client'

/**
 * CLR-042 — Public shared-analysis page body (/s/[shareId]).
 *
 * Renders the sanitized share payload: document type, language pair,
 * analysis date, the permanent legal disclaimer, summary, and clause
 * cards (SharedClauseCard — no source-text toggle by design; the
 * payload never contains document text).
 *
 * A sticky bottom CTA invites the reader to analyse their own contract.
 */

import { useState } from 'react'
import Link from 'next/link'
import { useTranslations, useFormatter } from 'next-intl'
import { LegalDisclaimer } from '@/components/ui/LegalDisclaimer'
import { DOCUMENT_LANGUAGES } from '@/components/forms/LanguageSelection'
import { SharedClauseCard, type SharedClause } from './SharedClauseCard'

export interface SharedAnalysisPayload {
  document_type: string
  summary: string
  clauses: SharedClause[]
  protective_clause_count: number
  review_clause_count: number
  doc_language: string
  output_language: string
  analysed_at: string | null
  expires_at: string
}

function languageName(code: string): string {
  return DOCUMENT_LANGUAGES.find((l) => l.code === code)?.name ?? code
}

export function SharedAnalysisView({ payload }: { payload: SharedAnalysisPayload }) {
  const t = useTranslations('sharedPage')
  const tResults = useTranslations('results')
  const format = useFormatter()

  const [expandedId, setExpandedId] = useState<string | null>(
    payload.clauses[0]?.id ?? null
  )

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Header — type, language pair, date. No share button, no user info. */}
      <header className="bg-white border-b border-neutral-100 px-4 py-3">
        <div className="max-w-2xl mx-auto">
          <p className="text-xs font-medium uppercase tracking-wide text-brand-700">
            {t('header_label')}
          </p>
          <p className="text-sm font-semibold text-neutral-900 mt-0.5">
            {tResults(`document_types.${payload.document_type}`, {
              fallback: tResults('document_types.default'),
            })}
          </p>
          <p className="text-xs text-neutral-500 mt-0.5">
            {tResults('language_pair', {
              from: languageName(payload.doc_language),
              to: languageName(payload.output_language),
            })}
            {payload.analysed_at && (
              <>
                {' · '}
                {t('analysed_on', {
                  date: format.dateTime(new Date(payload.analysed_at), {
                    dateStyle: 'medium',
                  }),
                })}
              </>
            )}
          </p>
        </div>
      </header>

      {/* Permanent, non-dismissable legal disclaimer */}
      <LegalDisclaimer />

      {/* pb-28 keeps the sticky CTA from covering the last clause card */}
      <main className="flex-1 max-w-2xl w-full mx-auto px-4 py-5 pb-28 flex flex-col gap-4">
        <section className="rounded-2xl bg-white border border-neutral-200 p-5">
          <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-500 mb-2">
            {tResults('summary_label')}
          </h2>
          <p className="font-serif text-[15px] leading-relaxed text-neutral-900">
            {payload.summary}
          </p>
          {(payload.protective_clause_count > 0 || payload.review_clause_count > 0) && (
            <div className="mt-4 flex gap-4 text-xs text-neutral-600">
              {payload.protective_clause_count > 0 && (
                <span>
                  {tResults('protective_count', {
                    count: payload.protective_clause_count,
                  })}
                </span>
              )}
              {payload.review_clause_count > 0 && (
                <span>
                  {tResults('review_count', { count: payload.review_clause_count })}
                </span>
              )}
            </div>
          )}
        </section>

        <section aria-label={tResults('clauses_label')} className="flex flex-col gap-3">
          {payload.clauses.map((clause, index) => (
            <SharedClauseCard
              key={clause.id}
              clause={clause}
              index={index}
              isExpanded={expandedId === clause.id}
              onToggleExpand={() =>
                setExpandedId((current) => (current === clause.id ? null : clause.id))
              }
            />
          ))}
        </section>
      </main>

      {/* Sticky conversion CTA */}
      <div className="fixed bottom-0 inset-x-0 z-40 bg-white border-t border-neutral-200 px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between gap-3">
          <p className="text-sm font-medium text-neutral-900 min-w-0">{t('cta_text')}</p>
          <Link
            href="/upload"
            className="
              shrink-0 px-4 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
              flex items-center
              hover:bg-brand-800 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
            "
          >
            {t('cta_button')}
          </Link>
        </div>
      </div>
    </div>
  )
}
