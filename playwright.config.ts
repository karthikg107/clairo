/**
 * CLR-054 — Playwright E2E configuration.
 *
 * Backend APIs are mocked per-test via page.route() — the suite verifies
 * the frontend's flows end-to-end without needing Postgres/Redis/Claude,
 * so it runs identically in CI and locally. Flows that need a REAL
 * signed-in Clerk session are gated on E2E_CLERK_KEYS (see
 * e2e/auth-boundary.spec.ts).
 *
 * Gate: `npx playwright test` must pass before any production deploy.
 */
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'mobile-chromium',
      // 375px-first product — test at the baseline viewport.
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: [
    {
      // Mock backend for SERVER-SIDE fetches (e.g. the /s/[shareId] page)
      // — page.route() only sees browser traffic. See e2e/mock-api.mjs.
      command: 'node e2e/mock-api.mjs',
      url: 'http://localhost:4010/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        // Point both server- and browser-side API calls at the mock API.
        // Browser calls are still intercepted per-test via page.route().
        API_URL: 'http://localhost:4010',
        NEXT_PUBLIC_API_URL: 'http://localhost:4010',
        // Bypass Clerk middleware — no Clerk instance in the E2E env
        // (see middleware.ts). The signed-in project is key-gated.
        NEXT_PUBLIC_E2E_MODE: '1',
      },
    },
  ],
})
