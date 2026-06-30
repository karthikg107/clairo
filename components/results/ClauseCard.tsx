'use client'

/**
 * CLR-018 — Single clause card on the analysis results screen.
 *
 * Tap header to expand/collapse. When expanded: flag badge, frequency stat,
 * explanation (Source Serif 4) with tappable numbers, and a toggle to reveal
 * the original document text (JetBrains Mono).
 */

import { useState, Fragment } from 'react'
import { useTranslations } from 'next-intl'
import { ChevronDown, ShieldCheck, AlertTriangle, FileText } from 'lucide-react'
import { cn } from '@/lib/utils/cn'
import { TappableNumber } from '@/components/results/NumberVerificationPanel'
import type { Clause, ClauseNumber } from './types'

interface ClauseCardProps {
  clause: Clause
  index: number
  isExpanded: boolean
  onToggleExpand: () => void
  onTapNumber: (number: ClauseNumber, clauseTitle: string) => void
}

function FlagBadge({ clause }: { clause: Clause }) {
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

/** Splits explanation text on each number's literal value and renders TappableNumber inline. */
function renderExplanation(
  text: string,
  numbers: ClauseNumber[],
  clauseTitle: string,
  onTapNumber: (number: ClauseNumber, clauseTitle: string) => void
) {
  if (numbers.length === 0) return text

  // Build a single pass split across all number values, longest first to avoid partial overlaps.
  const sorted = [...numbers].sort((a, b) => b.value.length - a.value.length)
  const parts: Array<string | ClauseNumber> = [text]

  for (const num of sorted) {
    const next: Array<string | ClauseNumber> = []
    for (const part of parts) {
      if (typeof part !== 'string') {
        next.push(part)
        continue
      }
      const segments = part.split(num.value)
      segments.forEach((seg, i) => {
        if (seg) next.push(seg)
        if (i < segments.length - 1) next.push(num)
      })
    }
    parts.length = 0
    parts.push(...next)
  }

  return parts.map((part, i) =>
    typeof part === 'string' ? (
      <Fragment key={i}>{part}</Fragment>
    ) : (
      <TappableNumber key={i} number={part} onTap={() => onTapNumber(part, clauseTitle)} />
    )
  )
}

export function ClauseCard({
  clause,
  index,
  isExpanded,
  onToggleExpand,
  onTapNumber,
}: ClauseCardProps) {
  const t = useTranslations('results')
  const [showOriginal, setShowOriginal] = useState(false)
  const panelId = `clause-panel-${clause.id}`

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
          <span className="text-xs text-neutral-400 font-medium">
            {t('clause_number', { n: index + 1 })}
          </span>
          <h3 className="text-sm font-semibold text-neutral-900 mt-0.5">{clause.title}</h3>
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
            'w-5 h-5 text-neutral-400 shrink-0 mt-1 transition-transform rtl:rotate-180',
            isExpanded && 'rotate-180 rtl:rotate-0'
          )}
          aria-hidden
        />
      </button>

      {isExpanded && (
        <div id={panelId} className="px-4 pb-4">
          <p className="font-serif text-[15px] leading-relaxed text-neutral-800">
            {renderExplanation(clause.explanation, clause.numbers, clause.title, onTapNumber)}
          </p>

          <button
            type="button"
            onClick={() => setShowOriginal((v) => !v)}
            aria-expanded={showOriginal}
            className="
              mt-3 inline-flex items-center gap-1.5
              text-xs font-medium text-brand-700 hover:text-brand-800
              focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500 focus-visible:rounded
            "
          >
            <FileText className="w-3.5 h-3.5" aria-hidden />
            {showOriginal ? t('hide_original') : t('show_original')}
          </button>

          {showOriginal && (
            <p className="mt-2 font-mono text-xs leading-relaxed text-neutral-600 bg-neutral-50 rounded-xl p-3 whitespace-pre-wrap">
              {clause.original_text}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
