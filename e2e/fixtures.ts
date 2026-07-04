/**
 * CLR-054 — shared mocks and fixtures.
 *
 * NO DOCUMENT CONTENT: every string here is obviously synthetic test
 * data ("SYNTHETIC-TEST-…"), never real contract text.
 */
import type { Page } from '@playwright/test'

export const SYNTHETIC_WORDS = [
  'SYNTHETIC-TEST-AGREEMENT',
  'clause',
  'one:',
  'the',
  'TEST-TENANT',
  'pays',
  '100',
  'EUR',
  'deposit.',
]

export const OCR_RESPONSE = {
  pages: [
    {
      page_number: 1,
      words: SYNTHETIC_WORDS.map((text, i) => ({
        text,
        confidence: i === 4 ? 0.4 : 0.98,
        confidence_level: i === 4 ? 'low' : i === 6 ? 'number' : 'high',
        bounding_box: null,
      })),
      low_confidence_ratio: 0.1,
    },
  ],
  total_pages: 1,
  source: 'gcv',
  skip_review: false,
}

export const CLASSIFY_RENTAL = {
  document_type: 'rental',
  is_prohibited: false,
  confidence: 0.97,
  reasoning: 'synthetic test classification',
  referral: null,
}

export const CLASSIFY_PROHIBITED = {
  document_type: 'court_order',
  is_prohibited: true,
  confidence: 0.99,
  reasoning: 'synthetic test classification',
  referral: {
    org: 'Test Legal Aid Organisation',
    url: 'https://example.org/legal-aid',
    reason_key: 'default',
  },
}

export const ANALYSE_RESPONSE = {
  document_type: 'rental',
  summary: 'SYNTHETIC-TEST-SUMMARY: a one-page test agreement with one deposit clause.',
  clauses: [
    {
      id: 'c1',
      title: 'Deposit',
      original_text: 'SYNTHETIC-TEST-EXCERPT deposit clause',
      explanation: 'SYNTHETIC-TEST-EXPLANATION: the tenant pays a deposit of 100 EUR.',
      frequency_pct: 60,
      is_protective: false,
      flag_level: 'review',
      numbers: [{ value: '100 EUR', context: 'deposit amount' }],
    },
  ],
  protective_clause_count: 0,
  review_clause_count: 1,
  analysis_id: null,
  quota: { allowed: true, is_free_tier: true, used: 1, limit: 2, remaining: 1 },
}

export const SHARED_RESPONSE = {
  document_type: 'rental',
  summary: 'SYNTHETIC-TEST-SUMMARY for a shared analysis page.',
  clauses: [
    {
      id: 'c1',
      title: 'Deposit',
      explanation: 'SYNTHETIC-TEST-EXPLANATION for the shared page.',
      frequency_pct: 60,
      is_protective: false,
      flag_level: 'review',
    },
  ],
  protective_clause_count: 0,
  review_clause_count: 1,
  doc_language: 'de',
  output_language: 'en',
  analysed_at: '2026-07-01T00:00:00+00:00',
  expires_at: '2026-08-01T00:00:00+00:00',
}

/** A tiny valid one-pixel PNG — a synthetic stand-in for a photographed page. */
export const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64'
)

// The mock API lives on :4010 while the app runs on :3000 — browser
// calls are cross-origin, so fulfilled responses need CORS headers and
// JSON POSTs need their OPTIONS preflight answered.
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'http://localhost:3000',
  'Access-Control-Allow-Credentials': 'true',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'content-type,authorization,x-anonymous-id',
}

async function fulfillJson(
  route: Parameters<Parameters<Page['route']>[1]>[0],
  body: object,
  status = 200
): Promise<void> {
  if (route.request().method() === 'OPTIONS') {
    await route.fulfill({ status: 204, headers: CORS_HEADERS })
    return
  }
  await route.fulfill({
    status,
    headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/** Mocks the happy-path backend for the upload → analysis flow. */
export async function mockAnalysisApis(
  page: Page,
  overrides: {
    ocr?: object
    classify?: object
    analyse?: { status?: number; body?: object }
  } = {}
): Promise<{ calls: string[] }> {
  const calls: string[] = []

  await page.route('**/api/v1/upload/validate', async (route) => {
    if (route.request().method() !== 'OPTIONS') calls.push('validate')
    await fulfillJson(route, { valid: true, error_code: null, message: null })
  })
  await page.route('**/api/v1/ocr', async (route) => {
    if (route.request().method() !== 'OPTIONS') calls.push('ocr')
    await fulfillJson(route, overrides.ocr ?? OCR_RESPONSE)
  })
  await page.route('**/api/v1/classify', async (route) => {
    if (route.request().method() !== 'OPTIONS') calls.push('classify')
    await fulfillJson(route, overrides.classify ?? CLASSIFY_RENTAL)
  })
  await page.route('**/api/v1/analyse', async (route) => {
    if (route.request().method() !== 'OPTIONS') calls.push('analyse')
    await fulfillJson(
      route,
      overrides.analyse?.body ?? ANALYSE_RESPONSE,
      overrides.analyse?.status ?? 200
    )
  })
  await page.route('**/api/v1/quota', async (route) => {
    if (route.request().method() !== 'OPTIONS') calls.push('quota')
    await fulfillJson(route, {
      allowed: true,
      is_free_tier: true,
      used: 0,
      limit: 2,
      remaining: 2,
    })
  })

  return { calls }
}

/** Selects the three languages on the LanguageSelection screen and submits. */
export async function completeLanguageSelection(page: Page): Promise<void> {
  // Accessible names come from the field labels (htmlFor → button id).
  await page.getByRole('button', { name: 'Document language', exact: true }).click()
  await page.getByRole('option', { name: /German/ }).click()

  await page.getByRole('button', { name: /^Country/ }).click()
  await page.getByRole('option', { name: 'Germany', exact: true }).click()

  await page.getByRole('button', { name: 'Explanation language', exact: true }).click()
  await page.getByRole('option', { name: 'English', exact: true }).click()

  await page.getByRole('button', { name: 'Analyse document' }).click()
}

/** Confirms the OCR review screen (mandatory checkbox + continue). */
export async function confirmOcrReview(page: Page): Promise<void> {
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Continue to Analysis' }).click()
}

/**
 * Dismisses the CLR-045 cookie-consent banner (fixed to the bottom edge,
 * it otherwise overlays bottom-of-page buttons). Declining also keeps
 * analytics fully off during E2E runs.
 */
export async function dismissConsent(page: Page): Promise<void> {
  await page
    .getByRole('region', { name: 'Cookie consent' })
    .getByRole('button', { name: 'Decline' })
    .click()
}
