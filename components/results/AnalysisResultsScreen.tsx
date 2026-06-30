'use client'

/**
 * CLR-018 — Analysis results screen (SCR-08).
 *
 * The most important screen in Clairo: presents the Claude-generated
 * analysis as a sticky header, a permanent legal disclaimer, a summary,
 * and a list of expandable clause cards in document order.
 *
 * Mobile-first (375px baseline). RTL handled via the ancestor `dir`
 * attribute set in app/[locale]/layout.tsx — this component only needs
 * to use logical (start/end) spacing and the `rtl:` Tailwind variant
 * for anything direction-sensitive (chevrons, icons).
 */

import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { Share2 } from 'lucide-react'
import { LegalDisclaimer } from '@/components/ui/LegalDisclaimer'
import { ClauseCard } from './ClauseCard'
import { ShareSheet } from './ShareSheet'
import { FindProfessionalCard } from './FindProfessionalCard'
import { UpgradePrompt } from './UpgradePrompt'
import { NumberVerificationPanel } from './NumberVerificationPanel'
import type { AnalysisResult, ClauseNumber } from './types'

// Reader is considered "engaged" once this many distinct clause cards
// have scrolled into view — the upgrade prompt is gated on this.
const UPGRADE_PROMPT_CLAUSE_THRESHOLD = 2

interface AnalysisResultsScreenProps {
  result: AnalysisResult
  docLanguageName: string
  outputLanguageName: string
  shareUrl: string
  professionalHref?: string
  isFreeTier: boolean
  onUpgrade: () => void
}

export function AnalysisResultsScreen({
  result,
  docLanguageName,
  outputLanguageName,
  shareUrl,
  professionalHref,
  isFreeTier,
  onUpgrade,
}: AnalysisResultsScreenProps) {
  const t = useTranslations('results')

  const [expandedId, setExpandedId] = useState<string | null>(
    result.clauses[0]?.id ?? null
  )
  const [shareOpen, setShareOpen] = useState(false)
  const [activeNumber, setActiveNumber] = useState<{
    number: ClauseNumber
    clauseTitle: string
  } | null>(null)
  const [seenClauseIds, setSeenClauseIds] = useState<Set<string>>(new Set())
  const [upgradeDismissed, setUpgradeDismissed] = useState(false)

  const clauseRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  // Track which clause cards have scrolled into view, to gate the upgrade prompt.
  useEffect(() => {
    if (!isFreeTier) return

    const observer = new IntersectionObserver(
      (entries) => {
        setSeenClauseIds((prev) => {
          const next = new Set(prev)
          let changed = false
          for (const entry of entries) {
            if (entry.isIntersecting) {
              const id = entry.target.getAttribute('data-clause-id')
              if (id && !next.has(id)) {
                next.add(id)
                changed = true
              }
            }
          }
          return changed ? next : prev
        })
      },
      { threshold: 0.5 }
    )

    clauseRefs.current.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [isFreeTier, result.clauses.length])

  const showUpgradePrompt =
    isFreeTier &&
    !upgradeDismissed &&
    seenClauseIds.size >= UPGRADE_PROMPT_CLAUSE_THRESHOLD

  const setClauseRef = useCallback((id: string, el: HTMLDivElement | null) => {
    if (el) clauseRefs.current.set(id, el)
    else clauseRefs.current.delete(id)
  }, [])

  const handleTapNumber = useCallback((number: ClauseNumber, clauseTitle: string) => {
    setActiveNumber({ number, clauseTitle })
  }, [])

  const protectiveCount = result.protective_clause_count
  const reviewCount = result.review_clause_count

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Sticky header */}
      <header className="sticky top-0 z-50 bg-white border-b border-neutral-100 px-4 py-3">
        <div className="flex items-center justify-between gap-3 max-w-2xl mx-auto">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-neutral-900 truncate">
              {t(`document_types.${result.document_type}`, {
                fallback: t('document_types.default'),
              })}
            </p>
            <p className="text-xs text-neutral-500 truncate">
              {t('language_pair', { from: docLanguageName, to: outputLanguageName })}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShareOpen(true)}
            aria-label={t('share_aria')}
            className="
              shrink-0 w-11 h-11 rounded-full flex items-center justify-center
              text-brand-700 hover:bg-brand-50 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
            "
          >
            <Share2 className="w-5 h-5" aria-hidden />
          </button>
        </div>
      </header>

      {/* Permanent, non-dismissable legal disclaimer */}
      <div className="sticky top-[57px] z-40">
        <LegalDisclaimer />
      </div>

      <main className="flex-1 max-w-2xl w-full mx-auto px-4 py-5 flex flex-col gap-4">
        {/* Summary card */}
        <section className="rounded-2xl bg-white border border-neutral-200 p-5">
          <h2 className="text-xs font-medium uppercase tracking-wide text-neutral-500 mb-2">
            {t('summary_label')}
          </h2>
          <p className="font-serif text-[15px] leading-relaxed text-neutral-900">
            {result.summary}
          </p>
          {(protectiveCount > 0 || reviewCount > 0) && (
            <div className="mt-4 flex gap-4 text-xs text-neutral-600">
              {protectiveCount > 0 && (
                <span>{t('protective_count', { count: protectiveCount })}</span>
              )}
              {reviewCount > 0 && <span>{t('review_count', { count: reviewCount })}</span>}
            </div>
          )}
        </section>

        {/* Clause cards, in document order */}
        <section aria-label={t('clauses_label')} className="flex flex-col gap-3">
          {result.clauses.map((clause, index) => (
            <div
              key={clause.id}
              data-clause-id={clause.id}
              ref={(el) => setClauseRef(clause.id, el)}
            >
              <ClauseCard
                clause={clause}
                index={index}
                isExpanded={expandedId === clause.id}
                onToggleExpand={() =>
                  setExpandedId((current) => (current === clause.id ? null : clause.id))
                }
                onTapNumber={handleTapNumber}
              />
            </div>
          ))}
        </section>

        <FindProfessionalCard href={professionalHref} />
      </main>

      {showUpgradePrompt && (
        <UpgradePrompt onUpgrade={onUpgrade} onDismiss={() => setUpgradeDismissed(true)} />
      )}

      {shareOpen && (
        <ShareSheet
          shareUrl={shareUrl}
          documentType={result.document_type}
          onClose={() => setShareOpen(false)}
        />
      )}

      {activeNumber && (
        <NumberVerificationPanel
          number={activeNumber.number}
          clauseTitle={activeNumber.clauseTitle}
          onClose={() => setActiveNumber(null)}
        />
      )}
    </div>
  )
}
