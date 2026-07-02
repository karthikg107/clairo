/**
 * CLR-027 — Pricing data, mirrored from backend/app/services/billing.py's
 * TIER_PRICING. Keep these numbers in sync manually — the backend is the
 * source of truth for what Stripe actually charges; this is presentation
 * only and never used to compute anything billed.
 */

export type PlanTier = 'free' | 'starter' | 'pro' | 'team'

export interface PricingPlan {
  tier: PlanTier
  monthlyUsd: number
  /** Total for the year when billed annually (25% off monthly * 12), not a monthly-equivalent. */
  annualUsd: number
}

export const ANNUAL_DISCOUNT_PCT = 25

export const PRICING_PLANS: PricingPlan[] = [
  { tier: 'free', monthlyUsd: 0, annualUsd: 0 },
  { tier: 'starter', monthlyUsd: 7, annualUsd: 63 },
  { tier: 'pro', monthlyUsd: 19, annualUsd: 171 },
  { tier: 'team', monthlyUsd: 49, annualUsd: 441 },
]

export function formatUsd(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: amount % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(amount)
}
