/**
 * CLR-054 — flow 3: free tier limits. When the lifetime quota is
 * exhausted the analyse call returns 402 and the flow shows the quota
 * screen with an upgrade CTA — never a broken error state.
 */
import { test, expect } from '@playwright/test'
import {
  mockAnalysisApis,
  dismissConsent,
  completeLanguageSelection,
  OCR_RESPONSE,
} from './fixtures'

test('quota-exhausted analyse (402) shows the upgrade screen', async ({ page }) => {
  await mockAnalysisApis(page, {
    ocr: { ...OCR_RESPONSE, source: 'direct', skip_review: true },
    analyse: {
      status: 402,
      body: {
        detail: {
          error: 'quota_exceeded',
          message: 'synthetic quota message',
          used: 2,
          limit: 2,
        },
      },
    },
  })

  await page.goto('/upload')
  await dismissConsent(page)
  await page.setInputFiles('input[type="file"] >> nth=0', {
    name: 'synthetic-test.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 synthetic test file'),
  })
  await completeLanguageSelection(page)

  await expect(page.getByText("You've used your free analyses")).toBeVisible()
  await expect(page.getByRole('link', { name: 'View plans' })).toBeVisible()
})
