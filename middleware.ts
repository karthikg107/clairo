import createMiddleware from 'next-intl/middleware'

export const locales = ['en', 'hi', 'de', 'es', 'ar', 'fr', 'pt', 'ur'] as const
export type Locale = (typeof locales)[number]

export const rtlLocales: Locale[] = ['ar', 'ur']

export default createMiddleware({
  locales,
  defaultLocale: 'en',
  localePrefix: 'as-needed',
  localeDetection: true,
})

export const config = {
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)'],
}
