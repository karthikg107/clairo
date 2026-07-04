/**
 * CLR-054 — flow 5: prohibited document blocking. A prohibited
 * classification must stop the flow BEFORE /analyse (no analysis, no
 * quota cost) and show the referral screen.
 */
import { test, expect } from '@playwright/test'
import {
  mockAnalysisApis,
  dismissConsent,
  completeLanguageSelection,
  CLASSIFY_PROHIBITED,
  OCR_RESPONSE,
} from './fixtures'

test('prohibited document never reaches /analyse and shows referral', async ({
  page,
}) => {
  const { calls } = await mockAnalysisApis(page, {
    ocr: { ...OCR_RESPONSE, source: 'direct', skip_review: true },
    classify: CLASSIFY_PROHIBITED,
  })

  await page.goto('/upload')
  await dismissConsent(page)
  await page.setInputFiles('input[type="file"] >> nth=0', {
    name: 'synthetic-test.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 synthetic test file'),
  })
  await completeLanguageSelection(page)

  // Referral organisation from the classification is shown…
  await expect(page.getByText('Test Legal Aid Organisation')).toBeVisible()

  // …and /analyse was NEVER called (also implies no quota consumption).
  expect(calls).toContain('classify')
  expect(calls).not.toContain('analyse')
})
