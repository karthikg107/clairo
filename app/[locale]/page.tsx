/**
 * CLR-046 — landing page route (/).
 *
 * Public — exempted from Clerk auth in middleware.ts. Localised by the
 * visitor's detected language/country: next-intl's middleware
 * (localeDetection) picks the locale from Accept-Language and this page
 * renders fully translated server-side.
 */
import { LandingPage } from '@/components/landing/LandingPage'

export default function HomePage({ params: { locale } }: { params: { locale: string } }) {
  return <LandingPage locale={locale} />
}
