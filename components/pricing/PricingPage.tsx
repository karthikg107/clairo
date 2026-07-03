'use client'

/**
 * CLR-027 — Pricing page (SCR-10).
 *
 * Four plan cards (Free, Starter, Pro, Team) with a monthly/annual toggle
 * showing the real 25% annual discount (see lib/pricing.ts, mirrored from
 * backend/app/services/billing.py's TIER_PRICING).
 *
 * No dark patterns: the toggle defaults to monthly (not pre-selected
 * annual to inflate the visible discount), the "Save 25%" badge reflects
 * the actual discount applied by Stripe, and there is no countdown timer,
 * fake scarcity, or pre-checked upsell anywhere on this page.
 *
 * Paid-tier CTAs call POST /api/v1/billing/checkout-session (CLR-026).
 * A brand-new subscriber gets a `checkout_url` to redirect to. An already
 * active/trialing subscriber instead gets `applied_immediately: true`
 * (CLR-028) — their existing Stripe subscription was changed in place with
 * proration, so we send them straight to the dashboard instead of through
 * Checkout again. Signed-out visitors are sent to sign-up first — Stripe
 * Checkout requires an account.
 */

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { useAuth } from '@clerk/nextjs'
import { Check, Loader2 } from 'lucide-react'
import { PRICING_PLANS, formatUsd, type PlanTier } from '@/lib/pricing'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

type Interval = 'monthly' | 'annual'

const PAID_TIERS: PlanTier[] = ['starter', 'pro', 'team']

export function PricingPage() {
  const t = useTranslations('pricingPage')
  const { isSignedIn, getToken } = useAuth()
  const router = useRouter()

  const [interval, setInterval] = useState<Interval>('monthly')
  const [loadingTier, setLoadingTier] = useState<PlanTier | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSelectPlan = useCallback(
    async (tier: PlanTier) => {
      if (tier === 'free') {
        router.push('/sign-up')
        return
      }

      if (!isSignedIn) {
        router.push('/sign-up')
        return
      }

      setError(null)
      setLoadingTier(tier)

      try {
        const token = await getToken()
        const res = await fetch(`${API_BASE}/api/v1/billing/checkout-session`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ tier, interval }),
        })

        if (!res.ok) throw new Error(`Checkout failed: ${res.status}`)

        const data: { checkout_url: string | null; applied_immediately: boolean } =
          await res.json()

        if (data.applied_immediately) {
          router.push('/dashboard?upgraded=true')
          return
        }

        if (data.checkout_url) {
          window.location.href = data.checkout_url
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        setLoadingTier(null)
      }
    },
    [interval, isSignedIn, getToken, router]
  )

  return (
    <main className="min-h-screen bg-background px-4 py-10">
      <div className="max-w-5xl mx-auto">
        {/* Heading */}
        <div className="text-center max-w-2xl mx-auto mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900 mb-3">
            {t('heading')}
          </h1>
          <p className="text-sm sm:text-base text-neutral-600">{t('subheading')}</p>
        </div>

        {/* Monthly / annual toggle — neither option pre-selected to mislead */}
        <div className="flex justify-center mb-10">
          <div
            role="group"
            aria-label={t('toggle.monthly') + ' / ' + t('toggle.annual')}
            className="inline-flex items-center rounded-2xl border border-neutral-200 bg-white p-1"
          >
            <button
              type="button"
              onClick={() => setInterval('monthly')}
              aria-pressed={interval === 'monthly'}
              className={`
                px-4 py-2 rounded-xl text-sm font-medium transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
                ${interval === 'monthly' ? 'bg-brand-700 text-white' : 'text-neutral-600 hover:text-neutral-900'}
              `}
            >
              {t('toggle.monthly')}
            </button>
            <button
              type="button"
              onClick={() => setInterval('annual')}
              aria-pressed={interval === 'annual'}
              className={`
                flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
                ${interval === 'annual' ? 'bg-brand-700 text-white' : 'text-neutral-600 hover:text-neutral-900'}
              `}
            >
              {t('toggle.annual')}
              <span
                className={`
                  text-[11px] font-semibold px-1.5 py-0.5 rounded-full
                  ${interval === 'annual' ? 'bg-white text-brand-700' : 'bg-accent-100 text-accent-700'}
                `}
              >
                {t('toggle.annual_badge')}
              </span>
            </button>
          </div>
        </div>

        {error && (
          <p className="text-center text-sm text-danger-600 mb-6" role="alert">
            {error}
          </p>
        )}

        {/* Plan cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {PRICING_PLANS.map((plan) => {
            const isPaid = PAID_TIERS.includes(plan.tier)
            const isTeam = plan.tier === 'team'
            const price = interval === 'annual' ? plan.annualUsd : plan.monthlyUsd
            const features = t.raw(`tiers.${plan.tier}.features`) as string[]

            return (
              <div
                key={plan.tier}
                className={`
                  flex flex-col rounded-2xl border p-5 text-start
                  ${isTeam ? 'border-brand-500 bg-white ring-1 ring-brand-500' : 'border-neutral-200 bg-white'}
                `}
              >
                <h2 className="text-sm font-semibold text-neutral-900">
                  {t(`tiers.${plan.tier}.name`)}
                </h2>
                <p className="text-xs text-neutral-500 mt-1 mb-4 leading-relaxed">
                  {t(`tiers.${plan.tier}.description`)}
                </p>

                <div className="mb-4">
                  {plan.tier === 'free' ? (
                    <span className="text-2xl font-bold text-neutral-900">
                      {t('free_price')}
                    </span>
                  ) : (
                    <>
                      <span className="text-2xl font-bold text-neutral-900">
                        {formatUsd(price)}
                      </span>
                      <span className="text-xs text-neutral-500 ms-1">
                        {interval === 'annual' ? t('per_year') : t('per_month')}
                      </span>
                    </>
                  )}
                </div>

                <ul className="flex flex-col gap-2 mb-6 flex-1">
                  {features.map((feature) => (
                    <li
                      key={feature}
                      className="flex items-start gap-2 text-xs text-neutral-700"
                    >
                      <Check
                        className="w-3.5 h-3.5 text-brand-600 shrink-0 mt-0.5"
                        aria-hidden
                      />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  onClick={() => handleSelectPlan(plan.tier)}
                  disabled={loadingTier === plan.tier}
                  className={`
                    w-full h-11 rounded-2xl text-sm font-semibold
                    flex items-center justify-center gap-2
                    transition-colors
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
                    disabled:opacity-60
                    ${
                      isTeam || isPaid
                        ? 'bg-brand-700 text-white hover:bg-brand-800'
                        : 'border border-neutral-200 text-neutral-700 hover:bg-neutral-50'
                    }
                  `}
                >
                  {loadingTier === plan.tier ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
                      {t('cta.signing_in')}
                    </>
                  ) : plan.tier === 'free' ? (
                    t('cta.free')
                  ) : (
                    t('cta.paid', { tier: t(`tiers.${plan.tier}.name`) })
                  )}
                </button>
              </div>
            )
          })}
        </div>

        <div className="text-center mt-8 space-y-1">
          <p className="text-xs text-neutral-500">{t('disclaimer')}</p>
          <p className="text-xs text-neutral-500">{t('not_legal_advice')}</p>
        </div>
      </div>
    </main>
  )
}
