/**
 * CLR-044 — referral landing route (/ref/[userId]).
 *
 * Public — stores the referrer id client-side and forwards the visitor
 * to sign-up. The referral is claimed after they create an account
 * (ReferralClaimer) and completes when they finish their first analysis.
 *
 * noindex — referral links are personal invitations, not search content.
 */
import type { Metadata } from 'next'
import { ReferralRedirect } from '@/components/referrals/ReferralRedirect'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Clairo',
    robots: { index: false, follow: false },
  }
}

interface PageProps {
  params: { userId: string }
}

export default function Page({ params }: PageProps) {
  return <ReferralRedirect referrerUserId={params.userId} />
}
