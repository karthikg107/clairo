'use client'

/**
 * CLR-023 — User dashboard with analysis history (SCR-11).
 *
 * Fetches the full history once (useAnalysisHistory) and does search +
 * filter-chip matching client-side — see lib/documentTypes.ts. Usage bar
 * and the free-tier upgrade banner reuse useQuota (CLR-025).
 */

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations, useFormatter } from 'next-intl'
import { Search, Upload, Sparkles } from 'lucide-react'
import { useAnalysisHistory, type AnalysisHistoryItem } from '@/hooks/useAnalysisHistory'
import { useQuota } from '@/hooks/useQuota'
import { DOCUMENT_LANGUAGES } from '@/components/forms/LanguageSelection'
import {
  FILTER_CHIPS,
  getDocumentTypeIcon,
  matchesFilter,
  type FilterChip,
} from '@/lib/documentTypes'

function languageName(code: string): string {
  return DOCUMENT_LANGUAGES.find((l) => l.code === code)?.name ?? code
}

export function DashboardPage() {
  const t = useTranslations('dashboard')
  const tDocTypes = useTranslations('results.document_types')
  const format = useFormatter()
  const router = useRouter()

  const { loading, items } = useAnalysisHistory()
  const quota = useQuota()

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<FilterChip>('all')

  const filteredItems = useMemo(() => {
    const query = search.trim().toLowerCase()

    return items.filter((item) => {
      if (!matchesFilter(item.documentType, filter)) return false
      if (!query) return true

      const typeLabel = tDocTypes(item.documentType, { fallback: tDocTypes('default') })
      const dateLabel = format.dateTime(new Date(item.createdAt), { dateStyle: 'medium' })
      return (
        typeLabel.toLowerCase().includes(query) ||
        dateLabel.toLowerCase().includes(query) ||
        item.summary.toLowerCase().includes(query)
      )
    })
  }, [items, search, filter, tDocTypes, format])

  const showUpgradeBanner = !quota.loading && quota.isFreeTier && !quota.allowed

  return (
    <div className="min-h-screen bg-background px-4 py-6">
      <div className="max-w-2xl mx-auto flex flex-col gap-5">
        {showUpgradeBanner && (
          <div className="rounded-2xl bg-brand-700 text-white p-4 flex items-start gap-3">
            <Sparkles className="w-5 h-5 shrink-0 text-accent-300 mt-0.5" aria-hidden />
            <div className="flex-1 min-w-0">
              <h2 className="text-sm font-semibold">{t('upgrade_banner.heading')}</h2>
              <p className="text-xs text-white/80 mt-0.5 leading-relaxed">
                {t('upgrade_banner.body')}
              </p>
            </div>
            <button
              type="button"
              onClick={() => router.push('/pricing')}
              className="
                shrink-0 px-3 py-1.5 rounded-xl bg-white text-brand-800 text-xs font-semibold
                hover:bg-brand-50 transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white
              "
            >
              {t('upgrade_banner.cta')}
            </button>
          </div>
        )}

        <div>
          <h1 className="text-xl font-bold text-neutral-900 mb-1">{t('heading')}</h1>

          {!quota.loading && (
            <div className="mt-3">
              {quota.isFreeTier ? (
                <>
                  <div className="flex items-center justify-between text-xs text-neutral-600 mb-1">
                    <span>{t('usage.label')}</span>
                    <span>
                      {t('usage.used_of_limit', { used: quota.used, limit: quota.limit })}
                    </span>
                  </div>
                  <div
                    role="progressbar"
                    aria-valuenow={quota.used}
                    aria-valuemin={0}
                    aria-valuemax={quota.limit}
                    aria-label={t('usage.label')}
                    className="h-2 rounded-full bg-neutral-100 overflow-hidden"
                  >
                    <div
                      className={`h-full rounded-full transition-all ${quota.allowed ? 'bg-brand-600' : 'bg-danger-500'}`}
                      style={{
                        width: `${Math.min(100, (quota.used / Math.max(quota.limit, 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </>
              ) : (
                <p className="text-xs text-neutral-500">{t('usage.unlimited')}</p>
              )}
            </div>
          )}
        </div>

        <div className="relative">
          <Search
            className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400"
            aria-hidden
          />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('search_placeholder')}
            aria-label={t('search_aria')}
            className="
              w-full h-11 ps-9 pe-3 rounded-2xl border border-neutral-200 bg-white
              text-sm text-neutral-900 placeholder:text-neutral-400
              focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
            "
          />
        </div>

        <div role="group" aria-label={t('search_aria')} className="flex flex-wrap gap-2">
          {FILTER_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => setFilter(chip)}
              aria-pressed={filter === chip}
              className={`
                px-3 py-1.5 rounded-full text-xs font-medium border transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
                ${
                  filter === chip
                    ? 'bg-brand-700 border-brand-700 text-white'
                    : 'bg-white border-neutral-200 text-neutral-600 hover:bg-neutral-50'
                }
              `}
            >
              {t(`filters.${chip}`)}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="text-sm text-neutral-500 text-center py-10">…</p>
        ) : items.length === 0 ? (
          <EmptyState
            heading={t('empty.heading')}
            body={t('empty.body')}
            cta={t('empty.cta')}
            onUpload={() => router.push('/upload')}
          />
        ) : filteredItems.length === 0 ? (
          <div className="text-center py-10">
            <h2 className="text-sm font-semibold text-neutral-900">
              {t('no_results.heading')}
            </h2>
            <p className="text-xs text-neutral-500 mt-1">{t('no_results.body')}</p>
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {filteredItems.map((item) => (
              <HistoryListItem
                key={item.id}
                item={item}
                typeLabel={tDocTypes(item.documentType, {
                  fallback: tDocTypes('default'),
                })}
                dateLabel={format.dateTime(new Date(item.createdAt), {
                  dateStyle: 'medium',
                })}
                itemAriaTemplate={t('item_aria', {
                  type: tDocTypes(item.documentType, { fallback: tDocTypes('default') }),
                  date: format.dateTime(new Date(item.createdAt), {
                    dateStyle: 'medium',
                  }),
                })}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function EmptyState({
  heading,
  body,
  cta,
  onUpload,
}: {
  heading: string
  body: string
  cta: string
  onUpload: () => void
}) {
  return (
    <div className="flex flex-col items-center text-center py-14 px-4">
      <div className="w-14 h-14 rounded-full bg-brand-50 flex items-center justify-center mb-4">
        <Upload className="w-6 h-6 text-brand-700" aria-hidden />
      </div>
      <h2 className="text-sm font-semibold text-neutral-900">{heading}</h2>
      <p className="text-xs text-neutral-500 mt-1 mb-5 max-w-xs">{body}</p>
      <button
        type="button"
        onClick={onUpload}
        className="
          px-5 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
          hover:bg-brand-800 transition-colors
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
        "
      >
        {cta}
      </button>
    </div>
  )
}

function HistoryListItem({
  item,
  typeLabel,
  dateLabel,
  itemAriaTemplate,
}: {
  item: AnalysisHistoryItem
  typeLabel: string
  dateLabel: string
  itemAriaTemplate: string
}) {
  const Icon = getDocumentTypeIcon(item.documentType)

  return (
    <li>
      <button
        type="button"
        aria-label={itemAriaTemplate}
        className="
          w-full flex items-center gap-3 rounded-2xl border border-neutral-200 bg-white p-4
          text-start hover:bg-neutral-50 transition-colors
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
        "
      >
        <div className="w-10 h-10 rounded-full bg-brand-50 flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 text-brand-700" aria-hidden />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-neutral-900 truncate">{typeLabel}</p>
          <p className="text-xs text-neutral-500 truncate">
            {languageName(item.docLanguage)} → {languageName(item.outputLanguage)}
          </p>
        </div>
        <span className="shrink-0 text-xs text-neutral-400">{dateLabel}</span>
      </button>
    </li>
  )
}
