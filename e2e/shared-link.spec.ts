/**
 * CLR-054 — flow 4: shared link. The /s/[shareId] page fetches
 * SERVER-side, so these tests are served by e2e/mock-api.mjs (a live
 * payload for LIVE_SHARE_ID, 404 for everything else) rather than
 * page.route().
 */
import { test, expect } from '@playwright/test'

const LIVE_SHARE_ID = '1b671a64-40d5-491e-99b0-da01ff1f3341'
const DEAD_SHARE_ID = '2c782b75-51e6-4a2f-a0c1-eb12aa2a4452'

test('live shared link renders sanitized analysis with sticky CTA', async ({ page }) => {
  await page.goto(`/s/${LIVE_SHARE_ID}`)

  await expect(page.getByText('SYNTHETIC-TEST-SUMMARY', { exact: false })).toBeVisible()
  await expect(page.getByText('Deposit').first()).toBeVisible()
  // Sticky conversion CTA
  await expect(page.getByRole('link', { name: 'Try Clairo free' })).toBeVisible()
  // noindex on shared pages — non-negotiable
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/)
  // The sanitized payload has no source text — the page must not offer one.
  await expect(page.getByText(/show original/i)).toHaveCount(0)
})

test('expired/revoked/unknown link shows the unavailable view', async ({ page }) => {
  await page.goto(`/s/${DEAD_SHARE_ID}`)

  await expect(page.getByText('This link is no longer available')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Analyse your contract' })).toBeVisible()
})
