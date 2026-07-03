'use client'

/**
 * CLR-044 — referral stats section on the account settings page.
 *
 * Shows the user's personal referral link (clairo.app/ref/[userId]) with
 * a copy button, plus completed invites, bonuses earned (of the max 10),
 * and total bonus analyses available.
 */

import { useState, useEffect, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { useAuth } from '@clerk/nextjs'
import { Copy, Check, Gift, Loader2 } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

interface ReferralStats {
  referral_path: string
  pending_count: number
  completed_count: number
  bonuses_earned: number
  max_bonuses: number
  bonus_analyses: number
}

export function ReferralSection() {
  const t = useTranslations('account.referrals')
  const { isLoaded, isSignedIn, getToken } = useAuth()

  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<ReferralStats | null>(null)
  const [copied, setCopied] = useState(false)

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [getToken])

  useEffect(() => {
    if (!isLoaded) return
    if (!isSignedIn) {
      setLoading(false)
      return
    }

    let cancelled = false
    const load = async () => {
      try {
        const headers = await authHeaders()
        const res = await fetch(`${API_BASE}/api/v1/referrals/stats`, {
          credentials: 'include',
          headers,
        })
        if (cancelled || !res.ok) return
        const data: ReferralStats = await res.json()
        if (!cancelled) setStats(data)
      } catch {
        // stats are non-critical — the section simply doesn't render
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [isLoaded, isSignedIn, authHeaders])

  if (loading) {
    return (
      <section className="rounded-2xl border border-neutral-200 bg-white p-5 flex justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-brand-600" aria-hidden />
      </section>
    )
  }

  if (!stats) return null

  const referralUrl = `${window.location.origin}${stats.referral_path}`

  const handleCopy = async () => {
    await navigator.clipboard.writeText(referralUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-5">
      <div className="flex items-center gap-2 mb-1">
        <Gift className="w-4 h-4 text-brand-700" aria-hidden />
        <h2 className="text-sm font-semibold text-neutral-900">{t('heading')}</h2>
      </div>
      <p className="text-xs text-neutral-500 mb-4 leading-relaxed">{t('body')}</p>

      {/* Referral link + copy */}
      <div className="flex items-center gap-2 mb-4">
        <code className="flex-1 min-w-0 truncate text-xs text-neutral-700 bg-neutral-50 border border-neutral-200 rounded-xl px-3 py-2.5">
          {referralUrl}
        </code>
        <button
          type="button"
          onClick={handleCopy}
          aria-label={t('copy_aria')}
          className="
            shrink-0 w-10 h-10 rounded-xl border border-neutral-200 flex items-center justify-center
            text-neutral-600 hover:bg-neutral-50 transition-colors
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
          "
        >
          {copied ? (
            <Check className="w-4 h-4 text-success-600" aria-hidden />
          ) : (
            <Copy className="w-4 h-4" aria-hidden />
          )}
        </button>
      </div>

      {/* Stats */}
      <dl className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-xl bg-neutral-50 p-3">
          <dt className="text-[11px] text-neutral-500">{t('stats.completed')}</dt>
          <dd className="text-lg font-bold text-neutral-900 mt-0.5">
            {stats.completed_count}
          </dd>
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <dt className="text-[11px] text-neutral-500">{t('stats.bonuses')}</dt>
          <dd className="text-lg font-bold text-neutral-900 mt-0.5">
            {t('stats.bonuses_value', {
              earned: stats.bonuses_earned,
              max: stats.max_bonuses,
            })}
          </dd>
        </div>
        <div className="rounded-xl bg-neutral-50 p-3">
          <dt className="text-[11px] text-neutral-500">{t('stats.available')}</dt>
          <dd className="text-lg font-bold text-neutral-900 mt-0.5">
            {stats.bonus_analyses}
          </dd>
        </div>
      </dl>
    </section>
  )
}
