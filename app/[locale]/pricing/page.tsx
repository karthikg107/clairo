/**
 * CLR-027 — Pricing page (SCR-10) route (/pricing).
 *
 * Public — exempted from Clerk auth in middleware.ts so signed-out
 * visitors can see pricing before creating an account.
 */
import type { Metadata } from 'next'
import { PricingPage } from '@/components/pricing/PricingPage'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Pricing — Clairo',
    description:
      'Simple, transparent pricing for understanding contracts in your language. Free, Starter, Pro, and Team plans.',
  }
}

export default function Page() {
  return <PricingPage />
}
