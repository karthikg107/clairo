/**
 * CLR-024 — Account settings route (/account).
 *
 * Authenticated only — not in middleware.ts's public-route matcher.
 */
import type { Metadata } from 'next'
import { AccountSettingsPage } from '@/components/account/AccountSettingsPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Account settings — Clairo',
    robots: { index: false, follow: false },
  }
}

export default function Page() {
  return <AccountSettingsPage />
}
