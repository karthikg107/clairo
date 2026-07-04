/**
 * CLR-049 — country-specific landing section.
 *
 * A local contract example (clause snippet → plain-language explanation,
 * synthetic — never a real document), a trusted local organisation, and
 * a local-currency price line for the most popular plan. Server
 * component; slots between the demo and how-it-works sections.
 */

import { getTranslations } from 'next-intl/server'
import { ExternalLink, MapPin } from 'lucide-react'
import { PRICING_PLANS } from '@/lib/pricing'
import {
  COUNTRY_LANDINGS,
  formatLocalPrice,
  type LandingCountry,
} from '@/lib/countryLanding'

export async function CountrySection({
  locale,
  country,
}: {
  locale: string
  country: LandingCountry
}) {
  const config = COUNTRY_LANDINGS[country]
  const t = await getTranslations({ locale, namespace: 'landing.countrySection' })
  const tc = await getTranslations({
    locale,
    namespace: `landing.countries.${config.i18nKey}`,
  })

  const proPlan = PRICING_PLANS.find((p) => p.tier === 'pro')
  const localPrice = proPlan ? formatLocalPrice(Number(proPlan.monthlyUsd), config) : null

  return (
    <section aria-labelledby="country-heading" className="bg-white px-4 py-12">
      <div className="mx-auto max-w-2xl">
        <div className="flex items-center justify-center gap-1.5 text-brand-700">
          <MapPin className="h-4 w-4" aria-hidden />
          <span className="text-xs font-semibold uppercase tracking-wide">
            {tc('label')}
          </span>
        </div>
        <h2
          id="country-heading"
          className="mt-2 text-center text-xl font-bold text-neutral-900"
        >
          {tc('heading')}
        </h2>

        {/* Local contract example — synthetic clause → plain language */}
        <div className="mt-6 rounded-2xl border border-neutral-200 p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">
            {t('example_label')}
          </p>
          <p className="mt-2 rounded-xl bg-neutral-50 p-3 font-mono text-xs leading-relaxed text-neutral-600">
            {tc('example_clause')}
          </p>
          <p className="mt-3 font-serif text-[15px] leading-relaxed text-neutral-800">
            {tc('example_explanation')}
          </p>
        </div>

        {/* Trusted local organisation */}
        <p className="mt-4 text-center text-xs leading-relaxed text-neutral-500">
          {t('org_line')}{' '}
          <a
            href={config.org.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-brand-700 hover:text-brand-800"
          >
            {config.org.name}
            <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        </p>

        {/* Local-currency price line */}
        {localPrice && (
          <p className="mt-2 text-center text-xs text-neutral-500">
            {t('price_line', { price: localPrice })}{' '}
            <span className="text-neutral-500">{t('price_note')}</span>
          </p>
        )}
      </div>
    </section>
  )
}
