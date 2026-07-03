/**
 * CLR-046 — landing page (SCR-01). Server component, zero client JS of
 * its own — CSS-only animations keep mobile Lighthouse performance high.
 *
 * Section order is mobile-first: on a 375px viewport the hero copy, CTA,
 * and the three trust signals all fit in the first screen (the animated
 * demo follows below the trust strip).
 */

import Link from 'next/link'
import { getTranslations } from 'next-intl/server'
import {
  Trash2,
  Lock,
  Globe,
  Upload,
  SearchCheck,
  MessageCircleQuestion,
  Home,
  Briefcase,
  Plane,
  Check,
} from 'lucide-react'
import { PRICING_PLANS, formatUsd } from '@/lib/pricing'
import { AnimatedDemo } from './AnimatedDemo'

const LANGUAGE_PAIRS: Array<{ from: string; to: string; dir?: 'rtl' }> = [
  { from: 'Deutsch', to: 'हिन्दी' },
  { from: 'English', to: 'العربية' },
  { from: 'Français', to: 'اردو' },
]

const TEASER_TIERS = ['starter', 'pro', 'team'] as const

export async function LandingPage({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: 'landing' })
  const tTiers = await getTranslations({ locale, namespace: 'pricingPage.tiers' })

  const trustSignals = [
    { icon: Trash2, key: 'deleted' },
    { icon: Lock, key: 'never_stored' },
    { icon: Globe, key: 'languages' },
  ] as const

  const steps = [
    { icon: Upload, key: 'upload' },
    { icon: SearchCheck, key: 'review' },
    { icon: MessageCircleQuestion, key: 'understand' },
  ] as const

  const useCases = [
    { icon: Home, key: 'renter' },
    { icon: Briefcase, key: 'job_switcher' },
    { icon: Plane, key: 'expat' },
  ] as const

  return (
    <main className="min-h-screen bg-background">
      {/* ── Hero — compact enough that the trust strip fits at 375px ────── */}
      <section className="px-4 pt-10 pb-6">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-3xl sm:text-4xl font-bold text-neutral-900 leading-tight">
            {t('hero.headline')}
          </h1>
          <p className="mt-3 text-base text-neutral-600">{t('hero.subheadline')}</p>
          <div className="mt-6 flex justify-center">
            <Link
              href="/upload"
              className="
                inline-flex h-12 items-center rounded-2xl bg-brand-700 px-6 text-base font-semibold text-white
                hover:bg-brand-800 transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
              "
            >
              {t('hero.cta')}
            </Link>
          </div>
          <p className="mt-2 text-xs text-neutral-500">{t('hero.cta_hint')}</p>
        </div>
      </section>

      {/* ── Trust strip — 3 signals, visible without scrolling at 375px ─── */}
      <section aria-label={t('trust.aria_label')} className="px-4 pb-8">
        <ul className="mx-auto flex max-w-2xl flex-row items-stretch justify-center gap-2 sm:gap-4">
          {trustSignals.map(({ icon: Icon, key }) => (
            <li
              key={key}
              className="flex flex-1 flex-col items-center gap-1.5 rounded-2xl border border-neutral-200 bg-white px-2 py-3 text-center"
            >
              <Icon className="h-4 w-4 text-brand-700" aria-hidden />
              <span className="text-[11px] font-medium leading-tight text-neutral-700">
                {t(`trust.${key}`)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {/* ── Animated demo ─────────────────────────────────────────────────── */}
      <section className="px-4 pb-12">
        <AnimatedDemo
          protectiveLabel={t('demo.protective')}
          reviewLabel={t('demo.review')}
          plainLabel={t('demo.plain')}
        />
      </section>

      {/* ── How it works — 3 steps ───────────────────────────────────────── */}
      <section aria-labelledby="how-heading" className="bg-white px-4 py-12">
        <div className="mx-auto max-w-2xl">
          <h2 id="how-heading" className="text-center text-xl font-bold text-neutral-900">
            {t('how.heading')}
          </h2>
          <ol className="mt-8 flex flex-col gap-6 sm:flex-row sm:gap-4">
            {steps.map(({ icon: Icon, key }, i) => (
              <li key={key} className="flex flex-1 flex-col items-center text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50">
                  <Icon className="h-6 w-6 text-brand-700" aria-hidden />
                </div>
                <span className="mt-2 text-xs font-semibold uppercase tracking-wide text-brand-700">
                  {t('how.step_label', { n: i + 1 })}
                </span>
                <h3 className="mt-1 text-sm font-semibold text-neutral-900">
                  {t(`how.${key}.title`)}
                </h3>
                <p className="mt-1 text-xs leading-relaxed text-neutral-500">
                  {t(`how.${key}.body`)}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ── Use cases ─────────────────────────────────────────────────────── */}
      <section aria-labelledby="usecases-heading" className="px-4 py-12">
        <div className="mx-auto max-w-2xl">
          <h2
            id="usecases-heading"
            className="text-center text-xl font-bold text-neutral-900"
          >
            {t('use_cases.heading')}
          </h2>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {useCases.map(({ icon: Icon, key }) => (
              <div
                key={key}
                className="rounded-2xl border border-neutral-200 bg-white p-5"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-50">
                  <Icon className="h-5 w-5 text-brand-700" aria-hidden />
                </div>
                <h3 className="mt-3 text-sm font-semibold text-neutral-900">
                  {t(`use_cases.${key}.title`)}
                </h3>
                <p className="mt-1 text-xs leading-relaxed text-neutral-500">
                  {t(`use_cases.${key}.body`)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Language showcase — rotating banner (CSS cycle) ─────────────── */}
      <section
        aria-label={t('languages.aria_label')}
        className="bg-brand-700 px-4 py-10 text-center text-white"
      >
        <p className="text-sm font-medium text-brand-100">{t('languages.heading')}</p>
        <div className="relative mx-auto mt-3 h-10 max-w-md" aria-hidden="true">
          {LANGUAGE_PAIRS.map((pair) => (
            <span
              key={pair.from}
              className="landing-language-pair absolute inset-0 flex items-center justify-center gap-3 text-2xl font-bold"
            >
              <span>{pair.from}</span>
              <span aria-hidden className="text-brand-300">
                →
              </span>
              <span>{pair.to}</span>
            </span>
          ))}
        </div>
        <p className="mt-3 text-xs text-brand-200">{t('languages.subtext')}</p>
      </section>

      {/* ── Pricing teaser — 3 paid plans ─────────────────────────────────── */}
      <section aria-labelledby="pricing-teaser-heading" className="px-4 py-12">
        <div className="mx-auto max-w-2xl">
          <h2
            id="pricing-teaser-heading"
            className="text-center text-xl font-bold text-neutral-900"
          >
            {t('pricing_teaser.heading')}
          </h2>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {TEASER_TIERS.map((tier) => {
              const plan = PRICING_PLANS.find((p) => p.tier === tier)
              if (!plan) return null
              return (
                <div
                  key={tier}
                  className="flex flex-col rounded-2xl border border-neutral-200 bg-white p-5"
                >
                  <h3 className="text-sm font-semibold text-neutral-900">
                    {tTiers(`${tier}.name`)}
                  </h3>
                  <p className="mt-2">
                    <span className="text-2xl font-bold text-neutral-900">
                      {formatUsd(plan.monthlyUsd)}
                    </span>
                    <span className="ms-1 text-xs text-neutral-500">
                      {t('pricing_teaser.per_month')}
                    </span>
                  </p>
                  <p className="mt-2 flex items-start gap-1.5 text-xs leading-relaxed text-neutral-500">
                    <Check
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600"
                      aria-hidden
                    />
                    {tTiers(`${tier}.description`)}
                  </p>
                </div>
              )
            })}
          </div>
          <div className="mt-6 text-center">
            <Link
              href="/pricing"
              className="text-sm font-semibold text-brand-700 hover:text-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:rounded"
            >
              {t('pricing_teaser.all_plans')}
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="border-t border-neutral-200 bg-white px-4 py-8">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
          <p className="text-xs text-neutral-500">{t('footer.disclaimer')}</p>
          <nav aria-label={t('footer.nav_aria')} className="flex gap-4 text-xs">
            <Link href="/privacy" className="text-neutral-500 hover:text-neutral-800">
              {t('footer.privacy')}
            </Link>
            <Link href="/terms" className="text-neutral-500 hover:text-neutral-800">
              {t('footer.terms')}
            </Link>
            <Link href="/pricing" className="text-neutral-500 hover:text-neutral-800">
              {t('footer.pricing')}
            </Link>
          </nav>
        </div>
      </footer>
    </main>
  )
}
