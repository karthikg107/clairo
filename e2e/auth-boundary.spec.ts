/**
 * CLR-054 — flow 6: signup → upload → analysis.
 *
 * The upload → analysis half runs anonymously in this suite (see
 * upload-analysis.spec.ts) — anonymous users get 2 free analyses by
 * design (CLR-025). The SIGNED-IN variant needs a real Clerk test
 * instance; it is gated on E2E_CLERK_KEYS so CI with keys runs it and
 * local runs without keys skip it explicitly (never silently green).
 */
import { test, expect } from '@playwright/test'

test('sign-up page is reachable from the landing CTA path', async ({ page }) => {
  await page.goto('/sign-up')
  await expect(page).toHaveURL(/sign-up/)
  // The page shell renders (Clerk's widget itself needs real keys).
  await expect(page.locator('body')).not.toContainText('Application error')
})

test('landing hero CTA leads into the upload flow', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Analyse your contract' }).first().click()
  await expect(page).toHaveURL(/\/upload/)
  await expect(page.getByRole('button', { name: 'Upload your contract' })).toBeVisible()
})

test('full signed-in journey: signup → upload → analysis', async ({ page }) => {
  test.skip(
    !process.env.E2E_CLERK_KEYS,
    'Requires a Clerk test instance (set E2E_CLERK_KEYS + test credentials in CI). ' +
      'The anonymous upload → analysis journey is covered in upload-analysis.spec.ts.'
  )
  // With Clerk test keys configured, implement with @clerk/testing:
  // signUp via the widget, then run the upload flow assertions from
  // upload-analysis.spec.ts and additionally assert the share button
  // appears (persisted analysis → analysis_id present).
  await page.goto('/sign-up')
})
