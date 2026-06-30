import { SignIn } from '@clerk/nextjs'
import { getTranslations } from 'next-intl/server'
import type { Metadata } from 'next'

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string }
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'auth' })
  return { title: t('sign_in.page_title') }
}

export default function SignInPage() {
  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12">
      {/* Brand mark */}
      <div className="mb-8 text-center">
        <span className="text-2xl font-bold text-brand-700 tracking-tight">
          clairo
        </span>
        <p className="mt-1 text-sm text-neutral-500">Contract clarity for everyone</p>
      </div>

      {/*
        Clerk renders magic link (email code) as the primary method.
        Google OAuth shows as a social button.
        Password is disabled — configure in Clerk Dashboard:
          User & Authentication → Email, Phone, Username → disable passwords
          Social connections → enable Google
          Magic links → enable
      */}
      <SignIn
        appearance={{
          elements: {
            // Outer card
            card: 'shadow-none border border-neutral-200 rounded-2xl w-full max-w-sm',
            // Header
            headerTitle: 'text-lg font-semibold text-neutral-900',
            headerSubtitle: 'text-sm text-neutral-500',
            // Social buttons
            socialButtonsBlockButton:
              'border border-neutral-200 rounded-xl text-sm font-medium text-neutral-700 hover:bg-neutral-50 transition-colors',
            // Divider
            dividerLine: 'bg-neutral-200',
            dividerText: 'text-neutral-400 text-xs',
            // Email input
            formFieldInput:
              'rounded-xl border-neutral-200 text-sm focus:border-brand-500 focus:ring-brand-500',
            formFieldLabel: 'text-sm font-medium text-neutral-700',
            // Primary action button
            formButtonPrimary:
              'bg-brand-700 hover:bg-brand-800 text-white rounded-xl text-sm font-semibold h-11 transition-colors',
            // Footer links
            footerActionLink: 'text-brand-700 hover:text-brand-800 font-medium',
            // Error messages
            formFieldErrorText: 'text-danger-600 text-xs',
            alertText: 'text-danger-600 text-sm',
          },
          variables: {
            colorPrimary: '#1B4F8A',
            colorDanger: '#B91C1C',
            borderRadius: '0.75rem',
            fontFamily: 'var(--font-inter)',
          },
        }}
      />

      <p className="mt-6 text-xs text-neutral-400 text-center max-w-xs">
        By signing in you agree to our{' '}
        <a href="/terms" className="underline hover:text-neutral-600">
          Terms of Service
        </a>{' '}
        and{' '}
        <a href="/privacy" className="underline hover:text-neutral-600">
          Privacy Policy
        </a>
        .
      </p>
    </main>
  )
}
