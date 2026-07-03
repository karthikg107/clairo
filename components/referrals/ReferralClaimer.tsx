'use client'

/**
 * CLR-044 — claims a stored referral once the visitor is signed in.
 *
 * Mounted globally in the [locale] layout; renders nothing. Runs once
 * per session when a referrer id is stored: POST /referrals/claim, then
 * clears the stored id whatever the outcome (a rejected claim — self-
 * referral, already claimed — will never succeed later, so retrying
 * would just spam the API).
 */

import { useEffect, useRef } from 'react'
import { useAuth } from '@clerk/nextjs'
import { readReferrer, clearReferrer } from '@/lib/referral'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export function ReferralClaimer() {
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const attempted = useRef(false)

  useEffect(() => {
    if (!isLoaded || !isSignedIn || attempted.current) return

    const referrerUserId = readReferrer()
    if (!referrerUserId) return
    attempted.current = true

    const claim = async () => {
      try {
        const token = await getToken()
        await fetch(`${API_BASE}/api/v1/referrals/claim`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ referrer_user_id: referrerUserId }),
        })
      } catch {
        // best-effort — an unclaimed referral is not worth surfacing an error
      } finally {
        clearReferrer()
      }
    }

    claim()
  }, [isLoaded, isSignedIn, getToken])

  return null
}
