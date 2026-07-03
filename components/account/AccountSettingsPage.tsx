'use client'

/**
 * CLR-024 — Account settings and GDPR data deletion (SCR-12-ish).
 *
 * Shows email, subscription tier, member-since date, and editable
 * language preferences (doc language / explanation language / country —
 * reuses the same option lists as the upload flow's LanguageSelection,
 * CLR-014). Also hosts the GDPR data export and the delete-account
 * danger zone (typed-confirmation dialog, backend re-validates the
 * same confirmation string).
 */

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations, useFormatter } from 'next-intl'
import { Download, Loader2 } from 'lucide-react'
import { useAccountSettings } from '@/hooks/useAccountSettings'
import {
  DOCUMENT_LANGUAGES,
  COUNTRIES,
  EXPLANATION_LANGUAGES,
} from '@/components/forms/LanguageSelection'
import { DeleteAccountDialog } from './DeleteAccountDialog'
import { ReferralSection } from './ReferralSection'
import { SubscriptionSection } from './SubscriptionSection'

export function AccountSettingsPage() {
  const t = useTranslations('account')
  const tTiers = useTranslations('pricingPage.tiers')
  const format = useFormatter()
  const router = useRouter()

  const {
    loading,
    account,
    saveLanguagePreferences,
    saving,
    saveError,
    exportData,
    deleteAccount,
  } = useAccountSettings()

  const [docLanguage, setDocLanguage] = useState('')
  const [outputLanguage, setOutputLanguage] = useState('')
  const [country, setCountry] = useState('')
  const [saved, setSaved] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)

  useEffect(() => {
    if (!account) return
    setDocLanguage(account.docLanguage ?? '')
    setOutputLanguage(account.outputLanguage ?? '')
    setCountry(account.country ?? '')
  }, [account])

  const handleSave = async () => {
    setSaved(false)
    try {
      await saveLanguagePreferences({ docLanguage, outputLanguage, country })
      setSaved(true)
    } catch {
      // saveError is already surfaced by the hook
    }
  }

  const handleExport = async () => {
    setExporting(true)
    setExportError(null)
    try {
      const data = await exportData()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'clairo-data-export.json'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteConfirmed = async () => {
    await deleteAccount('DELETE')
    router.push('/')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-brand-600" aria-hidden />
      </div>
    )
  }

  if (!account) {
    return null
  }

  return (
    <div className="min-h-screen bg-background px-4 py-6">
      <div className="max-w-xl mx-auto flex flex-col gap-6">
        <h1 className="text-xl font-bold text-neutral-900">{t('heading')}</h1>

        {/* Profile */}
        <section className="rounded-2xl border border-neutral-200 bg-white p-5">
          <dl className="flex flex-col gap-3 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-neutral-500">{t('email_label')}</dt>
              <dd className="text-neutral-900 font-medium">{account.email}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-neutral-500">{t('plan_label')}</dt>
              <dd className="text-neutral-900 font-medium">
                {tTiers(`${account.subscriptionTier}.name`, {
                  fallback: account.subscriptionTier,
                })}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-neutral-500">{t('member_since_label')}</dt>
              <dd className="text-neutral-900 font-medium">
                {format.dateTime(new Date(account.memberSince), { dateStyle: 'medium' })}
              </dd>
            </div>
          </dl>
        </section>

        {/* Subscription management (CLR-029) */}
        <SubscriptionSection />

        {/* Referral programme (CLR-044) */}
        <ReferralSection />

        {/* Language preferences */}
        <section className="rounded-2xl border border-neutral-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-neutral-900 mb-4">
            {t('language_preferences.heading')}
          </h2>

          <div className="flex flex-col gap-4">
            <div>
              <label
                htmlFor="doc-language-select"
                className="block text-xs font-medium text-neutral-600 mb-1.5"
              >
                {t('language_preferences.doc_language_label')}
              </label>
              <select
                id="doc-language-select"
                value={docLanguage}
                onChange={(e) => setDocLanguage(e.target.value)}
                className="w-full h-11 px-3 rounded-xl border border-neutral-200 text-sm text-neutral-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                <option value="">{t('language_preferences.not_set')}</option>
                {DOCUMENT_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.flag} {lang.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="output-language-select"
                className="block text-xs font-medium text-neutral-600 mb-1.5"
              >
                {t('language_preferences.output_language_label')}
              </label>
              <select
                id="output-language-select"
                value={outputLanguage}
                onChange={(e) => setOutputLanguage(e.target.value)}
                className="w-full h-11 px-3 rounded-xl border border-neutral-200 text-sm text-neutral-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                <option value="">{t('language_preferences.not_set')}</option>
                {EXPLANATION_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.display}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="country-select"
                className="block text-xs font-medium text-neutral-600 mb-1.5"
              >
                {t('language_preferences.country_label')}
              </label>
              <select
                id="country-select"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full h-11 px-3 rounded-xl border border-neutral-200 text-sm text-neutral-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                <option value="">{t('language_preferences.not_set')}</option>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {saveError && (
              <p className="text-xs text-danger-600" role="alert">
                {saveError}
              </p>
            )}
            {saved && !saveError && (
              <p className="text-xs text-success-600" role="status">
                {t('language_preferences.saved')}
              </p>
            )}

            <button
              type="button"
              onClick={handleSave}
              disabled={saving || (!docLanguage && !outputLanguage && !country)}
              className="
                self-start px-5 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
                hover:bg-brand-800 transition-colors
                flex items-center gap-2
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
                disabled:opacity-50
              "
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
              {t('language_preferences.save')}
            </button>
          </div>
        </section>

        {/* GDPR export */}
        <section className="rounded-2xl border border-neutral-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-neutral-900">
            {t('export.heading')}
          </h2>
          <p className="text-xs text-neutral-500 mt-1 mb-3 leading-relaxed">
            {t('export.body')}
          </p>
          {exportError && (
            <p className="text-xs text-danger-600 mb-2" role="alert">
              {exportError}
            </p>
          )}
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="
              px-4 h-10 rounded-2xl border border-neutral-200 text-sm font-medium text-neutral-700
              hover:bg-neutral-50 transition-colors
              flex items-center gap-2
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
              disabled:opacity-50
            "
          >
            {exporting ? (
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
            ) : (
              <Download className="w-4 h-4" aria-hidden />
            )}
            {t('export.cta')}
          </button>
        </section>

        {/* Danger zone */}
        <section className="rounded-2xl border border-danger-200 bg-danger-50 p-5">
          <h2 className="text-sm font-semibold text-danger-700">
            {t('danger_zone.heading')}
          </h2>
          <p className="text-xs text-danger-700/80 mt-1 mb-3 leading-relaxed">
            {t('danger_zone.body')}
          </p>
          <button
            type="button"
            onClick={() => setDeleteOpen(true)}
            className="
              px-4 h-10 rounded-2xl bg-danger-600 text-white text-sm font-semibold
              hover:bg-danger-700 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500 focus-visible:ring-offset-2
            "
          >
            {t('danger_zone.cta')}
          </button>
        </section>
      </div>

      {deleteOpen && (
        <DeleteAccountDialog
          onConfirm={handleDeleteConfirmed}
          onClose={() => setDeleteOpen(false)}
        />
      )}
    </div>
  )
}
