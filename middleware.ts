import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import createIntlMiddleware from 'next-intl/middleware'
import { NextRequest } from 'next/server'

export const locales = ['en', 'hi', 'de', 'es', 'ar', 'fr', 'pt', 'ur'] as const
export type Locale = (typeof locales)[number]

export const rtlLocales: Locale[] = ['ar', 'ur']

const intlMiddleware = createIntlMiddleware({
  locales,
  defaultLocale: 'en',
  localePrefix: 'as-needed',
  localeDetection: true,
})

// Routes that Clerk should NOT protect
const isPublicRoute = createRouteMatcher([
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
  // health check
  '/api/health',
])

export default clerkMiddleware(async (auth, req: NextRequest) => {
  if (!isPublicRoute(req)) {
    await auth().protect()
  }
  return intlMiddleware(req)
})

export const config = {
  matcher: [
    // Skip Next.js internals and all static files
    '/((?!_next|_vercel|.*\\..*).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
}
