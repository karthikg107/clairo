/**
 * CLR-037 — Find a Professional referral directory.
 *
 * Resolves a country + document type to a real-world organisation that can
 * give the user a second opinion (tenants' unions, employment tribunals,
 * bar associations, legal aid bodies). Mirrors the shape of
 * backend/app/services/document_type.py's PROHIBITED_REFERRALS.
 *
 * Lookup order (first match wins):
 *   1. SPECIFIC_REFERRALS   — keyed by "<country>:<documentType>"
 *   2. COUNTRY_ANY_REFERRALS — keyed by "<country>", applies to any document type
 *   3. GENERIC_BAR_ASSOCIATIONS — per-country bar/law-society fallback
 *   4. null — caller falls back to the generic translated CTA
 *
 * HARD RULE: GENERIC_BAR_ASSOCIATIONS is best-effort data compiled from
 * general knowledge of each country's national bar association. It has NOT
 * been legally verified and MUST be reviewed by legal/compliance before
 * these links are relied upon in production (same requirement as the
 * hardcoded system prompt in backend/app/services/analysis.py).
 */

export interface Referral {
  org: string
  url: string
}

// ── 1. Country + document-type specific referrals ─────────────────────────────

const SPECIFIC_REFERRALS: Record<string, Referral> = {
  'DE:rental': {
    org: "Deutscher Mieterbund (German Tenants' Association)",
    url: 'https://www.mieterbund.de/',
  },
  'GB:rental': {
    org: 'Citizens Advice',
    url: 'https://www.citizensadvice.org.uk/housing/',
  },
  'GB:employment': {
    org: 'Acas',
    url: 'https://www.acas.org.uk/',
  },
  'AE:employment': {
    org: 'UAE Ministry of Human Resources and Emiratisation (MOHRE)',
    url: 'https://www.mohre.gov.ae/',
  },
}

// ── 2. Country-wide referrals (any permitted document type) ───────────────────

const COUNTRY_ANY_REFERRALS: Record<string, Referral> = {
  US: {
    org: 'American Bar Association — Find Legal Help',
    url: 'https://www.americanbar.org/groups/legal_services/flh-home/',
  },
  IN: {
    org: 'National Legal Services Authority (NALSA)',
    url: 'https://nalsa.gov.in/',
  },
}

// ── 3. Generic per-country bar association fallback ───────────────────────────
// Covers every country offered in components/forms/LanguageSelection.tsx's
// COUNTRIES list. US and IN are handled above via COUNTRY_ANY_REFERRALS.

const GENERIC_BAR_ASSOCIATIONS: Record<string, Referral> = {
  GB: {
    org: 'The Law Society of England and Wales',
    url: 'https://www.lawsociety.org.uk/',
  },
  DE: {
    org: 'Bundesrechtsanwaltskammer (Federal Bar of Germany)',
    url: 'https://www.brak.de/',
  },
  ES: { org: 'Consejo General de la Abogacía Española', url: 'https://www.abogacia.es/' },
  MX: { org: 'Barra Mexicana, Colegio de Abogados', url: 'https://www.bma.org.mx/' },
  FR: { org: 'Conseil National des Barreaux', url: 'https://www.cnb.avocat.fr/' },
  BR: { org: 'Ordem dos Advogados do Brasil (OAB)', url: 'https://www.oab.org.br/' },
  CA: { org: 'Federation of Law Societies of Canada', url: 'https://flsc.ca/' },
  AU: { org: 'Law Council of Australia', url: 'https://www.lawcouncil.au/' },
  PK: { org: 'Pakistan Bar Council', url: 'https://www.pakistanbarcouncil.org/' },
  BD: { org: 'Bangladesh Bar Council', url: 'https://www.bangladeshbarcouncil.org.bd/' },
  NG: { org: 'Nigerian Bar Association', url: 'https://nba.org.ng/' },
  ZA: { org: 'Law Society of South Africa', url: 'https://www.lssa.org.za/' },
  KE: { org: 'Law Society of Kenya', url: 'https://lsk.or.ke/' },
  GH: { org: 'Ghana Bar Association', url: 'https://ghanabar.org/' },
  AE: { org: 'UAE Ministry of Justice', url: 'https://www.moj.gov.ae/' },
  SA: { org: 'Saudi Bar Association', url: 'https://www.sba.gov.sa/' },
  EG: { org: 'Egyptian Bar Association', url: 'https://www.egyptianbar.org.eg/' },
  MA: { org: 'Ministère de la Justice (Morocco)', url: 'https://www.justice.gov.ma/' },
  AR: {
    org: 'Colegio Público de Abogados de la Capital Federal',
    url: 'https://www.cpacf.org.ar/',
  },
  CL: { org: 'Colegio de Abogados de Chile', url: 'https://www.colegioabogados.cl/' },
  CO: {
    org: 'Colegio Nacional de Abogados de Colombia',
    url: 'https://www.conalbos.org/',
  },
  PE: { org: 'Colegio de Abogados de Lima', url: 'https://www.cal.org.pe/' },
  IT: {
    org: 'Consiglio Nazionale Forense',
    url: 'https://www.consiglionazionaleforense.it/',
  },
  NL: { org: 'Nederlandse Orde van Advocaten', url: 'https://www.advocatenorde.nl/' },
  PL: { org: 'Naczelna Rada Adwokacka', url: 'https://www.nra.pl/' },
  RU: {
    org: 'Federal Chamber of Lawyers of the Russian Federation',
    url: 'https://fparf.ru/',
  },
  TR: {
    org: 'Türkiye Barolar Birliği (Union of Turkish Bar Associations)',
    url: 'https://www.barobirlik.org.tr/',
  },
  JP: {
    org: 'Japan Federation of Bar Associations',
    url: 'https://www.nichibenren.or.jp/',
  },
  KR: { org: 'Korean Bar Association', url: 'https://www.koreanbar.or.kr/' },
  CN: { org: 'All China Lawyers Association', url: 'http://www.acla.org.cn/' },
  TW: { org: 'Taiwan Bar Association', url: 'https://www.twba.org.tw/' },
  SG: { org: 'The Law Society of Singapore', url: 'https://www.lawsociety.org.sg/' },
  MY: { org: 'Malaysian Bar', url: 'https://www.malaysianbar.org.my/' },
  ID: { org: 'Perhimpunan Advokat Indonesia (PERADI)', url: 'https://www.peradi.or.id/' },
  TH: { org: 'Lawyers Council of Thailand', url: 'https://www.lct.or.th/' },
  VN: { org: 'Vietnam Bar Federation', url: 'https://en.liendoanluatsu.org.vn/' },
  PH: { org: 'Integrated Bar of the Philippines', url: 'https://ibp.ph/' },
  NZ: { org: 'New Zealand Law Society', url: 'https://www.lawsociety.org.nz/' },
  PT: { org: 'Ordem dos Advogados', url: 'https://www.oa.pt/' },
}

/**
 * Resolve the best-available professional referral for a given country and
 * (permitted) document type. Returns null only if the country isn't in any
 * of the tables above — the caller should fall back to a generic CTA.
 */
export function getProfessionalReferral(
  country: string,
  documentType: string
): Referral | null {
  const countryCode = country.toUpperCase()

  return (
    SPECIFIC_REFERRALS[`${countryCode}:${documentType}`] ??
    COUNTRY_ANY_REFERRALS[countryCode] ??
    GENERIC_BAR_ASSOCIATIONS[countryCode] ??
    null
  )
}
