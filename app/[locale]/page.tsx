/**
 * CLR-046/CLR-049 — landing page route (/).
 *
 * Public — exempted from Clerk auth in middleware.ts. Localised by the
 * visitor's detected language/country: next-intl's middleware
 * (localeDetection) picks the locale from Accept-Language, and the
 * middleware additionally redirects first-time visitors to their
 * country page (/de, /uk, /in, /ae) based on IP-geolocation headers.
 *
 * /de doubles as the Germany country page: German locale + the
 * Germany-specific section (lease example, Mieterverein, EUR).
 */
import type { Metadata } from 'next'
import { setRequestLocale } from 'next-intl/server'
import { locales } from '@/lib/locales'
import { LandingPage } from '@/components/landing/LandingPage'

// hreflang alternates (CLR-049): every locale variant of the global
// landing plus the country pages, with an x-default fallback.
const LANGUAGE_ALTERNATES: Record<string, string> = {
  ...Object.fromEntries(locales.map((l) => [l, l === 'en' ? '/' : `/${l}`])),
  'en-GB': '/uk',
  'en-IN': '/in',
  'en-AE': '/ae',
  'de-DE': '/de',
  'x-default': '/',
}

export async function generateMetadata(): Promise<Metadata> {
  return {
    alternates: { languages: LANGUAGE_ALTERNATES },
  }
}

export default function HomePage({ params: { locale } }: { params: { locale: string } }) {
  // CLR-050 — static rendering: the landing page prerenders per locale.
  setRequestLocale(locale)
  return <LandingPage locale={locale} country={locale === 'de' ? 'DE' : undefined} />
}
