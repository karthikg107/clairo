import { getRequestConfig } from 'next-intl/server'
import { notFound } from 'next/navigation'
import { locales, type Locale } from '@/middleware'

export default getRequestConfig(async ({ locale }) => {
  if (!locales.includes(locale as Locale)) notFound()

  return {
    messages: (await import(`@/locales/${locale}/common/index.json`)).default,
  }
})
