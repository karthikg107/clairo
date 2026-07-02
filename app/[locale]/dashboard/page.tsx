/**
 * CLR-023 — User dashboard (SCR-11) route (/dashboard).
 *
 * Authenticated only — not in middleware.ts's public-route matcher, so
 * signed-out visitors are redirected to sign-in by Clerk. This is also
 * where Clerk redirects after sign-in/sign-up (NEXT_PUBLIC_CLERK_AFTER_
 * SIGN_IN_URL / _SIGN_UP_URL, see .env.local.example).
 */
import type { Metadata } from 'next'
import { DashboardPage } from '@/components/dashboard/DashboardPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Dashboard — Clairo',
    robots: { index: false, follow: false },
  }
}

export default function Page() {
  return <DashboardPage />
}
