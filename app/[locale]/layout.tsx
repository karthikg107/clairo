import type { Metadata } from 'next'
import { ClerkProvider } from '@clerk/nextjs'
import { NextIntlClientProvider } from 'next-intl'
import { getMessages, getTranslations } from 'next-intl/server'
import { Inter, Source_Serif_4, JetBrains_Mono } from 'next/font/google'
import { notFound } from 'next/navigation'
import { locales, rtlLocales, type Locale } from '@/middleware'
import { cn } from '@/lib/utils'
import { ReferralClaimer } from '@/components/referrals/ReferralClaimer'
import '../globals.css'

const inter = Inter({
  subsets: ['latin', 'latin-ext'],
  variable: '--font-inter',
  display: 'swap',
})

const sourceSerif4 = Source_Serif_4({
  subsets: ['latin', 'latin-ext'],
  variable: '--font-source-serif',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin', 'latin-ext'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
})

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }))
}

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string }
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'meta' })
  return {
    title: t('title'),
    description: t('description'),
  }
}

export default async function LocaleLayout({
  children,
  params: { locale },
}: {
  children: React.ReactNode
  params: { locale: string }
}) {
  if (!locales.includes(locale as Locale)) notFound()

  const messages = await getMessages()
  const isRtl = rtlLocales.includes(locale as Locale)

  return (
    <ClerkProvider>
      <html
        lang={locale}
        dir={isRtl ? 'rtl' : 'ltr'}
        className={cn(inter.variable, sourceSerif4.variable, jetbrainsMono.variable)}
      >
        <body>
          <NextIntlClientProvider messages={messages}>
            {/* CLR-044 — claims a stored referral once signed in; renders nothing */}
            <ReferralClaimer />
            {children}
          </NextIntlClientProvider>
        </body>
      </html>
    </ClerkProvider>
  )
}
