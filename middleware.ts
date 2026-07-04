import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import createIntlMiddleware from 'next-intl/middleware'
import { NextRequest } from 'next/server'

// Locale constants live in lib/locales.ts (CLR-050) so client/server code
// can import them without pulling middleware dependencies into its graph.
// Re-exported here for backwards compatibility.
import { locales } from '@/lib/locales'

export { locales, rtlLocales, type Locale } from '@/lib/locales'

const intlMiddleware = createIntlMiddleware({
  locales,
  defaultLocale: 'en',
  localePrefix: 'as-needed',
  localeDetection: true,
})

// Routes that Clerk should NOT protect
const isPublicRoute = createRouteMatcher([
  // landing page (CLR-046) — root and locale-prefixed root only (the
  // explicit locale alternation avoids '/:locale' swallowing '/dashboard')
  '/',
  `/(${locales.join('|')})`,
  // i18n-prefixed sign-in / sign-up
  '/:locale/sign-in(.*)',
  '/:locale/sign-up(.*)',
  // default locale (no prefix)
  '/sign-in(.*)',
  '/sign-up(.*)',
  // static / legal pages
  '/privacy(.*)',
  '/terms(.*)',
  '/:locale/privacy(.*)',
  '/:locale/terms(.*)',
  // pricing (CLR-027) — must be visible before sign-up
  '/pricing(.*)',
  '/:locale/pricing(.*)',
  // shared analyses (CLR-042) — recipients have no account
  '/s/(.*)',
  '/:locale/s/(.*)',
  // referral landing (CLR-044) — visitors have no account yet
  '/ref/(.*)',
  '/:locale/ref/(.*)',
  // upload flow (CLR-054) — anonymous users get 2 free analyses (CLR-025)
  '/upload(.*)',
  '/:locale/upload(.*)',
  // health check
  '/api/health',
])

// CLR-054 — E2E mode: the Playwright suite runs without a Clerk instance
// (clerkMiddleware rejects browser requests outright on a placeholder
// key). Set ONLY by playwright.config.ts's webServer env — never in any
// deployment environment. Auth-dependent behavior is still covered: the
// signed-in E2E project requires real Clerk test keys (E2E_CLERK_KEYS).
const isE2EMode = process.env.NEXT_PUBLIC_E2E_MODE === '1'

const clerkHandler = clerkMiddleware(async (auth, req: NextRequest) => {
  if (!isPublicRoute(req)) {
    await auth().protect()
  }
  return intlMiddleware(req)
})

export default isE2EMode
  ? function e2eMiddleware(req: NextRequest) {
      return intlMiddleware(req)
    }
  : clerkHandler

export const config = {
  matcher: [
    // Skip Next.js internals and all static files
    '/((?!_next|_vercel|.*\\..*).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
}
