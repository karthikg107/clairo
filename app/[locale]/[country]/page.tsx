/**
 * CLR-049 — country landing routes (/uk, /in, /ae).
 *
 * A dynamic [country] segment inside the locale tree: with the
 * 'as-needed' locale prefix, /uk resolves as locale=en + country=uk.
 * Only the three country slugs are valid — any other single unknown
 * segment matches here (dynamic beats the [...rest] catch-all) and
 * falls through to notFound(), rendering the localized 404 exactly
 * like the catch-all does for deeper paths.
 *
 * Germany's page is /de — the German-locale landing with the country
 * section (see app/[locale]/page.tsx).
 */
import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { setRequestLocale } from 'next-intl/server'
import { COUNTRY_SLUG_TO_CODE } from '@/lib/countryLanding'
import { LandingPage } from '@/components/landing/LandingPage'

const HREFLANG_BY_SLUG: Record<string, string> = {
  uk: 'en-GB',
  in: 'en-IN',
  ae: 'en-AE',
}

export function generateStaticParams() {
  return Object.keys(COUNTRY_SLUG_TO_CODE).map((country) => ({ country }))
}

interface PageProps {
  params: { locale: string; country: string }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const hreflang = HREFLANG_BY_SLUG[params.country]
  if (!hreflang) return {}
  return {
    alternates: {
      canonical: `/${params.country}`,
      languages: {
        [hreflang]: `/${params.country}`,
        'x-default': '/',
      },
    },
  }
}

export default function CountryLandingPage({ params }: PageProps) {
  const country = COUNTRY_SLUG_TO_CODE[params.country]
  if (!country) notFound()

  setRequestLocale(params.locale)
  return <LandingPage locale={params.locale} country={country} />
}
