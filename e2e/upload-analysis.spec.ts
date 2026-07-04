/**
 * CLR-054 — flows 1 & 2: PDF upload → analysis, and image → OCR review
 * → analysis. Backend mocked (see fixtures.ts) — fixtures contain only
 * synthetic strings, never document content.
 */
import { test, expect } from '@playwright/test'
import {
  mockAnalysisApis,
  dismissConsent,
  completeLanguageSelection,
  confirmOcrReview,
  OCR_RESPONSE,
  TINY_PNG,
} from './fixtures'

test('PDF upload goes straight to analysis (review skipped) and paints results', async ({
  page,
}) => {
  const started = Date.now()
  await mockAnalysisApis(page, {
    // PDF/DOCX: direct extraction, review screen skipped by design
    ocr: { ...OCR_RESPONSE, source: 'direct', skip_review: true },
  })

  await page.goto('/upload')
  await dismissConsent(page)
  await page.setInputFiles('input[type="file"] >> nth=0', {
    name: 'synthetic-test.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 synthetic test file'),
  })

  // Review must be SKIPPED — language selection appears directly.
  await expect(page.getByRole('button', { name: 'Analyse document' })).toBeVisible()
  await completeLanguageSelection(page)

  // Results screen with the synthetic summary + clause.
  await expect(page.getByText('SYNTHETIC-TEST-SUMMARY', { exact: false })).toBeVisible()
  await expect(page.getByText('Deposit').first()).toBeVisible()

  // CLR-054 gate: the whole journey completes well under 60s in test env.
  expect(Date.now() - started).toBeLessThan(60_000)
})

test('image upload requires OCR review before analysis', async ({ page }) => {
  await mockAnalysisApis(page)

  await page.goto('/upload')
  await dismissConsent(page)
  await page.setInputFiles('input[type="file"] >> nth=0', {
    name: 'synthetic-test.png',
    mimeType: 'image/png',
    buffer: TINY_PNG,
  })

  // Review screen is mandatory for images — heading + confirm checkbox.
  await expect(page.getByText('Review Your Document')).toBeVisible()
  // The synthetic OCR words are shown for correction.
  await expect(page.getByText('SYNTHETIC-TEST-AGREEMENT')).toBeVisible()

  // Continue is disabled until the mandatory checkbox is ticked.
  await expect(page.getByRole('button', { name: 'Continue to Analysis' })).toBeDisabled()

  await confirmOcrReview(page)
  await completeLanguageSelection(page)

  await expect(page.getByText('SYNTHETIC-TEST-SUMMARY', { exact: false })).toBeVisible()
})

test('camera option opens the capture screen', async ({ page }) => {
  await mockAnalysisApis(page)
  await page.goto('/upload')
  await dismissConsent(page)

  await page.getByRole('button', { name: /Open camera/i }).click()
  // CameraCapture takes over (getUserMedia will fail without a device —
  // the component must surface its fallback UI rather than crash).
  await expect(
    page.getByRole('button', { name: /close|back|cancel/i }).first()
  ).toBeVisible({ timeout: 10_000 })
})
