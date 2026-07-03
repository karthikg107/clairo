'use client'

/**
 * CLR-045 — analytics lifecycle, mounted once in the locale layout.
 *
 * - Initializes PostHog on mount IF consent was previously granted.
 * - Shows the consent banner while the choice is undecided.
 * - Tracks page_view on every route change (pathname only — never query
 *   strings, which could carry tokens or ids).
 */

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import {
  getConsent,
  grantConsent,
  denyConsent,
  initAnalytics,
  track,
  type ConsentState,
} from '@/lib/analytics'
import { ConsentBanner } from './ConsentBanner'

export function AnalyticsProvider() {
  const pathname = usePathname()
  const [consent, setConsentState] = useState<ConsentState | null>(null)

  // Read consent client-side only (avoids SSR/localStorage mismatch).
  useEffect(() => {
    const state = getConsent()
    setConsentState(state)
    if (state === 'granted') initAnalytics()
  }, [])

  useEffect(() => {
    if (consent === 'granted' && pathname) {
      track('page_view', { path: pathname })
    }
  }, [pathname, consent])

  if (consent !== 'undecided') return null

  return (
    <ConsentBanner
      onAccept={() => {
        grantConsent()
        setConsentState('granted')
      }}
      onDecline={() => {
        denyConsent()
        setConsentState('denied')
      }}
    />
  )
}
