/**
 * CLR-050 — locale constants as a leaf module.
 *
 * Previously these lived in middleware.ts, so every importer (layout,
 * i18n request config, types) pulled the Clerk + next-intl middleware
 * modules into its graph. Keeping them here means importers get three
 * constants and nothing else.
 */

export const locales = ['en', 'hi', 'de', 'es', 'ar', 'fr', 'pt', 'ur'] as const
export type Locale = (typeof locales)[number]

export const rtlLocales: Locale[] = ['ar', 'ur']
