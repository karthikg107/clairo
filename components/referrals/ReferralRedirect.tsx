'use client'

/**
 * CLR-044 — stores the referrer id and forwards to sign-up.
 * Rendered by /ref/[userId]; visible only for the moment the redirect takes.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { storeReferrer } from '@/lib/referral'

export function ReferralRedirect({ referrerUserId }: { referrerUserId: string }) {
  const router = useRouter()

  useEffect(() => {
    storeReferrer(referrerUserId)
    router.replace('/sign-up')
  }, [referrerUserId, router])

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <Loader2 className="w-6 h-6 animate-spin text-brand-600" aria-hidden />
    </div>
  )
}
