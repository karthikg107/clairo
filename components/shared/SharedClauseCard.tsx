'use client'

/**
 * CLR-042 — Clause card on the PUBLIC shared-analysis page.
 *
 * Renders only what the sanitized share payload contains: title,
 * plain-language explanation, frequency stat, and flag badges.
 * There is deliberately NO source-text toggle and NO tappable numbers —
 * the backend never serves original_text or numbers on share links
 * (CLR-041), and this card has no affordance suggesting they exist.
 */

import { useTranslations } from 'next-intl'
import { ChevronDown, ShieldCheck, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils/cn'

export interface SharedClause {
  id: string
  title: string
  explanation: string
  frequency_pct: number | null
  is_protective: boolean
  flag_level: 'none' | 'note' | 'review'
}

interface SharedClauseCardProps {
  clause: SharedClause
  index: number
  isExpanded: boolean
  onToggleExpand: () => void
}

function FlagBadge({ clause }: { clause: SharedClause }) {
  const t = useTranslations('results.flags')

  if (clause.is_protective) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-success-50 text-success-700 text-xs font-medium px-2.5 py-1">
        <ShieldCheck className="w-3.5 h-3.5" aria-hidden />
        {t('protective')}
      </span>
    )
  }

  if (clause.flag_level === 'note' || clause.flag_level === 'review') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-warning-50 text-warning-700 text-xs font-medium px-2.5 py-1">
        <AlertTriangle className="w-3.5 h-3.5" aria-hidden />
        {clause.flag_level === 'review' ? t('review') : t('uncommon')}
      </span>
    )
  }

  return null
}

export function SharedClauseCard({
  clause,
  index,
  isExpanded,
  onToggleExpand,
}: SharedClauseCardProps) {
  const t = useTranslations('results')
  const panelId = `shared-clause-panel-${clause.id}`

  return (
    <div className="rounded-2xl border border-neutral-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={onToggleExpand}
        aria-expanded={isExpanded}
        aria-controls={panelId}
        className="
          w-full flex items-start justify-between gap-3
          px-4 py-4 min-h-touch text-start
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-inset
        "
      >
        <div className="flex-1 min-w-0">
          <span className="text-xs text-neutral-500 font-medium">
            {t('clause_number', { n: index + 1 })}
          </span>
          <h3 className="text-sm font-semibold text-neutral-900 mt-0.5">
            {clause.title}
          </h3>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <FlagBadge clause={clause} />
            {clause.frequency_pct !== null && (
              <span className="text-xs text-neutral-500">
                {t('frequency_stat', { pct: clause.frequency_pct })}
              </span>
            )}
          </div>
        </div>
        <ChevronDown
          className={cn(
            'w-5 h-5 text-neutral-500 shrink-0 mt-1 transition-transform rtl:rotate-180',
            isExpanded && 'rotate-180 rtl:rotate-0'
          )}
          aria-hidden
        />
      </button>

      {isExpanded && (
        <div id={panelId} className="px-4 pb-4">
          <p className="font-serif text-[15px] leading-relaxed text-neutral-800">
            {clause.explanation}
          </p>
        </div>
      )}
    </div>
  )
}
