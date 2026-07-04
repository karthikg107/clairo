/**
 * CLR-049 — country-localised landing content.
 *
 * Four launch countries with local contract examples, a trusted local
 * organisation, and local-currency price display. Everything else falls
 * back to the global (English/USD) landing.
 *
 * Currency amounts are DISPLAY-ONLY approximations of the USD prices
 * (billing itself is USD via Stripe) — rates are intentionally static
 * and conservative; the UI marks them "approx".
 */

export type LandingCountry = 'DE' | 'GB' | 'IN' | 'AE'

export interface CountryLandingConfig {
  country: LandingCountry
  /** URL segment: clairo.app/<slug> */
  slug: string
  /** i18n key under landing.countries.* */
  i18nKey: string
  /** Trusted local organisation referenced on the page */
  org: { name: string; url: string }
  currency: {
    code: string
    /** static display-only conversion from USD */
    ratePerUsd: number
    /** e.g. "€{amount}" — {amount} replaced with the converted price */
    format: string
  }
}

export const COUNTRY_LANDINGS: Record<LandingCountry, CountryLandingConfig> = {
  DE: {
    country: 'DE',
    slug: 'de', // the German-locale landing doubles as the Germany page
    i18nKey: 'de',
    org: {
      name: 'Deutscher Mieterbund (Mieterverein)',
      url: 'https://www.mieterbund.de',
    },
    currency: { code: 'EUR', ratePerUsd: 0.93, format: '€{amount}' },
  },
  GB: {
    country: 'GB',
    slug: 'uk',
    i18nKey: 'uk',
    org: { name: 'Citizens Advice', url: 'https://www.citizensadvice.org.uk' },
    currency: { code: 'GBP', ratePerUsd: 0.79, format: '£{amount}' },
  },
  IN: {
    country: 'IN',
    slug: 'in',
    i18nKey: 'in',
    org: {
      name: 'National Legal Services Authority (NALSA)',
      url: 'https://nalsa.gov.in',
    },
    currency: { code: 'INR', ratePerUsd: 84, format: '₹{amount}' },
  },
  AE: {
    country: 'AE',
    slug: 'ae',
    i18nKey: 'ae',
    org: {
      name: 'MOHRE (Ministry of Human Resources & Emiratisation)',
      url: 'https://www.mohre.gov.ae',
    },
    currency: { code: 'AED', ratePerUsd: 3.67, format: 'AED {amount}' },
  },
}

/** Country slugs that get their own top-level route (/uk, /in, /ae). */
export const COUNTRY_SLUG_TO_CODE: Record<string, LandingCountry> = {
  uk: 'GB',
  in: 'IN',
  ae: 'AE',
}

/** IP-geolocation country header → landing path (middleware redirect). */
export const GEO_COUNTRY_TO_PATH: Record<string, string> = {
  DE: '/de',
  GB: '/uk',
  IN: '/in',
  AE: '/ae',
}

export function formatLocalPrice(usd: number, config: CountryLandingConfig): string {
  const converted = usd * config.currency.ratePerUsd
  // Round to a "clean" local amount for display.
  const rounded = converted >= 100 ? Math.round(converted) : Math.round(converted * 2) / 2
  return config.currency.format.replace('{amount}', String(rounded))
}
