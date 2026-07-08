'use client'

/**
 * CLR-014 — Language selection screen (SCR-03).
 *
 * Three searchable dropdowns:
 *  1. Document language  — 20+ languages with flag emoji
 *  2. Country            — 40+ countries, tooltip explains legal context
 *  3. Explanation language — shown in English AND native script
 *
 * CTA disabled until all 3 fields are set.
 * Confidence indicator appears after document language + country are selected.
 * Mobile-first at 375px. WCAG 2.1 AA throughout.
 */

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'

// ── Data ──────────────────────────────────────────────────────────────────────

export const DOCUMENT_LANGUAGES = [
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'hi', name: 'Hindi', flag: '🇮🇳' },
  { code: 'de', name: 'German', flag: '🇩🇪' },
  { code: 'es', name: 'Spanish', flag: '🇪🇸' },
  { code: 'ar', name: 'Arabic', flag: '🇸🇦' },
  { code: 'fr', name: 'French', flag: '🇫🇷' },
  { code: 'pt', name: 'Portuguese', flag: '🇧🇷' },
  { code: 'ur', name: 'Urdu', flag: '🇵🇰' },
  { code: 'zh-cn', name: 'Chinese (Simplified)', flag: '🇨🇳' },
  { code: 'zh-tw', name: 'Chinese (Traditional)', flag: '🇹🇼' },
  { code: 'ja', name: 'Japanese', flag: '🇯🇵' },
  { code: 'ko', name: 'Korean', flag: '🇰🇷' },
  { code: 'it', name: 'Italian', flag: '🇮🇹' },
  { code: 'nl', name: 'Dutch', flag: '🇳🇱' },
  { code: 'pl', name: 'Polish', flag: '🇵🇱' },
  { code: 'ru', name: 'Russian', flag: '🇷🇺' },
  { code: 'tr', name: 'Turkish', flag: '🇹🇷' },
  { code: 'vi', name: 'Vietnamese', flag: '🇻🇳' },
  { code: 'th', name: 'Thai', flag: '🇹🇭' },
  { code: 'id', name: 'Indonesian', flag: '🇮🇩' },
  { code: 'ms', name: 'Malay', flag: '🇲🇾' },
  { code: 'bn', name: 'Bengali', flag: '🇧🇩' },
  { code: 'ta', name: 'Tamil', flag: '🇮🇳' },
  { code: 'te', name: 'Telugu', flag: '🇮🇳' },
] as const

export const COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'IN', name: 'India' },
  { code: 'DE', name: 'Germany' },
  { code: 'ES', name: 'Spain' },
  { code: 'MX', name: 'Mexico' },
  { code: 'FR', name: 'France' },
  { code: 'BR', name: 'Brazil' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'PK', name: 'Pakistan' },
  { code: 'BD', name: 'Bangladesh' },
  { code: 'NG', name: 'Nigeria' },
  { code: 'ZA', name: 'South Africa' },
  { code: 'KE', name: 'Kenya' },
  { code: 'GH', name: 'Ghana' },
  { code: 'AE', name: 'United Arab Emirates' },
  { code: 'SA', name: 'Saudi Arabia' },
  { code: 'EG', name: 'Egypt' },
  { code: 'MA', name: 'Morocco' },
  { code: 'AR', name: 'Argentina' },
  { code: 'CL', name: 'Chile' },
  { code: 'CO', name: 'Colombia' },
  { code: 'PE', name: 'Peru' },
  { code: 'IT', name: 'Italy' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'PL', name: 'Poland' },
  { code: 'RU', name: 'Russia' },
  { code: 'TR', name: 'Turkey' },
  { code: 'JP', name: 'Japan' },
  { code: 'KR', name: 'South Korea' },
  { code: 'CN', name: 'China' },
  { code: 'TW', name: 'Taiwan' },
  { code: 'SG', name: 'Singapore' },
  { code: 'MY', name: 'Malaysia' },
  { code: 'ID', name: 'Indonesia' },
  { code: 'TH', name: 'Thailand' },
  { code: 'VN', name: 'Vietnam' },
  { code: 'PH', name: 'Philippines' },
  { code: 'NZ', name: 'New Zealand' },
  { code: 'PT', name: 'Portugal' },
] as const

// Explanation languages shown in English AND native script
export const EXPLANATION_LANGUAGES = [
  { code: 'en', display: 'English' },
  { code: 'hi', display: 'Hindi — हिन्दी' },
  { code: 'de', display: 'German — Deutsch' },
  { code: 'es', display: 'Spanish — Español' },
  { code: 'ar', display: 'Arabic — العربية' },
  { code: 'fr', display: 'French — Français' },
  { code: 'pt', display: 'Portuguese — Português' },
  { code: 'ur', display: 'Urdu — اردو' },
  { code: 'zh-cn', display: 'Chinese (Simplified) — 简体中文' },
  { code: 'zh-tw', display: 'Chinese (Traditional) — 繁體中文' },
  { code: 'ja', display: 'Japanese — 日本語' },
  { code: 'ko', display: 'Korean — 한국어' },
  { code: 'it', display: 'Italian — Italiano' },
  { code: 'nl', display: 'Dutch — Nederlands' },
  { code: 'pl', display: 'Polish — Polski' },
  { code: 'ru', display: 'Russian — Русский' },
  { code: 'tr', display: 'Turkish — Türkçe' },
] as const

// High-confidence language+country pairings (simplified)
const HIGH_CONFIDENCE_PAIRS = new Set([
  'en-US',
  'en-GB',
  'en-AU',
  'en-CA',
  'en-NZ',
  'hi-IN',
  'de-DE',
  'es-ES',
  'es-MX',
  'es-AR',
  'fr-FR',
  'pt-BR',
  'pt-PT',
  'ar-SA',
  'ar-AE',
  'ar-EG',
  'ur-PK',
  'zh-cn-CN',
  'zh-tw-TW',
  'ja-JP',
  'ko-KR',
  'it-IT',
  'nl-NL',
  'pl-PL',
  'ru-RU',
  'tr-TR',
])

function getConfidence(docLang: string, country: string): 'high' | 'medium' | null {
  if (!docLang || !country) return null
  const key = `${docLang}-${country}`
  return HIGH_CONFIDENCE_PAIRS.has(key) ? 'high' : 'medium'
}

// ── SearchableSelect ──────────────────────────────────────────────────────────

interface Option {
  value: string
  label: string
  sublabel?: string
}

interface SearchableSelectProps {
  id: string
  label: string
  placeholder: string
  options: Option[]
  value: string
  onChange: (val: string) => void
  tooltip?: string
  required?: boolean
}

function SearchableSelect({
  id,
  label,
  placeholder,
  options,
  value,
  onChange,
  tooltip,
  required,
}: SearchableSelectProps) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [tipOpen, setTipOpen] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)

  // Focus management for the just-opened popup — an effect rather than
  // the autoFocus attribute (jsx-a11y/no-autofocus): focus moves only on
  // the explicit open action, never on page load.
  useEffect(() => {
    if (open) searchRef.current?.focus()
  }, [open])

  const filtered = useMemo(
    () =>
      options.filter(
        (o) =>
          o.label.toLowerCase().includes(query.toLowerCase()) ||
          (o.sublabel ?? '').toLowerCase().includes(query.toLowerCase())
      ),
    [options, query]
  )

  const selected = options.find((o) => o.value === value)

  const choose = (val: string) => {
    onChange(val)
    setOpen(false)
    setQuery('')
  }

  return (
    <div className="relative">
      <label
        htmlFor={id}
        className="flex items-center gap-1 text-sm font-medium text-dark-800 mb-1"
      >
        {label}
        {required && (
          <span className="text-danger-600" aria-hidden>
            *
          </span>
        )}
        {tooltip && (
          <button
            type="button"
            // preventDefault: this button lives inside the <label>, so a
            // click would otherwise also focus the select. We only want it
            // to toggle the help text — which now actually works on touch
            // (the old title= tooltip never appeared on mobile).
            onClick={(e) => {
              e.preventDefault()
              setTipOpen((o) => !o)
            }}
            aria-label={tooltip}
            aria-expanded={tipOpen}
            className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-dark-200 text-dark-600 text-[10px] leading-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            ?
          </button>
        )}
      </label>

      {tooltip && tipOpen && (
        <div
          role="tooltip"
          className="mb-2 rounded-lg bg-dark-800 text-white text-xs leading-snug px-3 py-2"
        >
          {tooltip}
        </div>
      )}

      <button
        type="button"
        id={id}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={[
          'w-full min-h-[48px] px-3 text-left rounded-lg border text-sm',
          'flex items-center justify-between gap-2',
          'focus:outline-none focus:ring-2 focus:ring-brand-500 focus-visible:ring-2',
          selected
            ? 'border-brand-500 bg-white text-dark-900'
            : 'border-dark-300 bg-white text-dark-400',
        ].join(' ')}
      >
        <span className="truncate">{selected ? selected.label : placeholder}</span>
        <span aria-hidden className="text-dark-400 shrink-0">
          ▾
        </span>
      </button>

      {open && (
        <div
          className="absolute z-50 left-0 right-0 mt-1 bg-white border border-dark-200 rounded-lg shadow-lg overflow-hidden"
          role="listbox"
          aria-label={label}
        >
          <div className="p-2 border-b border-dark-100">
            <input
              ref={searchRef}
              type="search"
              className="w-full text-sm px-3 py-2 border border-dark-200 rounded focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Search…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label={`Search ${label}`}
            />
          </div>
          <ul className="max-h-52 overflow-y-auto">
            {filtered.length === 0 && (
              <li className="px-4 py-3 text-sm text-dark-500">No results</li>
            )}
            {filtered.map((opt) => (
              <li
                key={opt.value}
                role="option"
                aria-selected={opt.value === value}
                tabIndex={0}
                onClick={() => choose(opt.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    choose(opt.value)
                  }
                }}
                className={[
                  'px-4 py-3 text-sm cursor-pointer',
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-inset hover:bg-brand-50',
                  opt.value === value
                    ? 'bg-brand-50 font-medium text-brand-700'
                    : 'text-dark-900',
                ].join(' ')}
              >
                <span>{opt.label}</span>
                {opt.sublabel && (
                  <span className="ml-1 text-dark-400">{opt.sublabel}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Confidence badge ──────────────────────────────────────────────────────────

function ConfidenceBadge({ level }: { level: 'high' | 'medium' }) {
  const t = useTranslations('language_selection')
  if (level === 'high') {
    return (
      <div
        role="status"
        className="flex items-center gap-1.5 text-xs text-success-700 bg-success-50 border border-success-200 rounded-full px-3 py-1 w-fit"
      >
        <span aria-hidden className="text-success-600">
          ✓
        </span>
        {t('confidence.high')}
      </div>
    )
  }
  return (
    <div
      role="status"
      className="flex items-center gap-1.5 text-xs text-warning-700 bg-warning-50 border border-warning-200 rounded-full px-3 py-1 w-fit"
    >
      <span aria-hidden>~</span>
      {t('confidence.medium')}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export interface LanguageSelectionValues {
  documentLanguage: string
  country: string
  explanationLanguage: string
}

export interface LanguageSelectionProps {
  onSubmit: (values: LanguageSelectionValues) => void
  initialValues?: Partial<LanguageSelectionValues>
}

export function LanguageSelection({
  onSubmit,
  initialValues = {},
}: LanguageSelectionProps) {
  const t = useTranslations('language_selection')
  const formId = useId()

  const [docLang, setDocLang] = useState(initialValues.documentLanguage ?? '')
  const [country, setCountry] = useState(initialValues.country ?? '')
  const [explLang, setExplLang] = useState(initialValues.explanationLanguage ?? '')

  const confidence = getConfidence(docLang, country)
  const canSubmit = docLang !== '' && country !== '' && explLang !== ''

  const docLangOptions: Option[] = DOCUMENT_LANGUAGES.map((l) => ({
    value: l.code,
    label: `${l.flag} ${l.name}`,
  }))

  const countryOptions: Option[] = COUNTRIES.map((c) => ({
    value: c.code,
    label: c.name,
  }))

  const explLangOptions: Option[] = EXPLANATION_LANGUAGES.map((l) => ({
    value: l.code,
    label: l.display,
  }))

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    onSubmit({ documentLanguage: docLang, country, explanationLanguage: explLang })
  }

  return (
    <form
      id={formId}
      onSubmit={handleSubmit}
      className="flex flex-col min-h-screen bg-background px-4 pt-6 pb-8"
      noValidate
    >
      <h1 className="text-xl font-bold text-dark-900 mb-1">{t('heading')}</h1>
      <p className="text-sm text-dark-600 mb-6">{t('subheading')}</p>

      <div className="space-y-5 flex-1">
        {/* 1. Document language */}
        <SearchableSelect
          id="doc-lang"
          label={t('doc_lang.label')}
          placeholder={t('doc_lang.placeholder')}
          options={docLangOptions}
          value={docLang}
          onChange={setDocLang}
          required
        />

        {/* 2. Country / legal context */}
        <SearchableSelect
          id="country"
          label={t('country.label')}
          placeholder={t('country.placeholder')}
          options={countryOptions}
          value={country}
          onChange={setCountry}
          tooltip={t('country.tooltip')}
          required
        />

        {/* Confidence badge — shown after doc lang + country set */}
        {confidence && <ConfidenceBadge level={confidence} />}

        {/* 3. Explanation language */}
        <SearchableSelect
          id="expl-lang"
          label={t('expl_lang.label')}
          placeholder={t('expl_lang.placeholder')}
          options={explLangOptions}
          value={explLang}
          onChange={setExplLang}
          required
        />
      </div>

      {/* CTA — disabled until all 3 fields set */}
      <button
        type="submit"
        disabled={!canSubmit}
        aria-disabled={!canSubmit}
        className={[
          'mt-8 w-full min-h-[52px] rounded-xl text-base font-semibold',
          'focus:outline-none focus:ring-2 focus:ring-brand-500 focus-visible:ring-2',
          canSubmit
            ? 'bg-brand-600 text-white hover:bg-brand-700 motion-safe:transition-colors'
            : 'bg-dark-200 text-dark-400 cursor-not-allowed',
        ].join(' ')}
      >
        {t('cta')}
      </button>

      <p className="mt-3 text-xs text-center text-dark-400">{t('cta_hint')}</p>
    </form>
  )
}

export default LanguageSelection
