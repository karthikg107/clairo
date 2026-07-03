/**
 * CLR-045 — privacy-safe PostHog analytics.
 *
 * PRIVACY (non-negotiable):
 * - Nothing is initialized or sent until the user grants consent via the
 *   cookie banner (ConsentBanner). No consent → no PostHog, full stop.
 * - No document content in any event — event properties are limited to
 *   the whitelisted metadata passed at each call site (method, document
 *   type, language codes; never text, filenames, or extracted content).
 * - No PII: we never call posthog.identify() with email/name. PostHog's
 *   randomly generated anonymous distinct_id is the only user identifier.
 * - autocapture and session recording are OFF — only the explicit,
 *   whitelisted events below are ever captured.
 *
 * PERFORMANCE (CLR-050): posthog-js is loaded via dynamic import ONLY
 * after consent is granted — visitors who decline (or never answer)
 * never download the analytics bundle at all.
 */

import type { PostHog } from 'posthog-js'

const CONSENT_KEY = 'clairo_analytics_consent'

export type ConsentState = 'granted' | 'denied' | 'undecided'

/** The complete set of events Clairo tracks — nothing else is ever sent. */
export type AnalyticsEvent =
  | 'page_view'
  | 'upload_started'
  | 'upload_completed'
  | 'analysis_started'
  | 'analysis_completed'
  | 'analysis_shared'
  | 'upgrade_prompted'
  | 'upgrade_completed'

let client: PostHog | null = null
let initializing = false
// Events fired between grantConsent() and the async init finishing are
// queued so nothing racing the dynamic import is lost.
let pending: Array<{ event: AnalyticsEvent; properties?: Record<string, unknown> }> = []

export function getConsent(): ConsentState {
  if (typeof window === 'undefined') return 'undecided'
  try {
    const value = window.localStorage.getItem(CONSENT_KEY)
    return value === 'granted' || value === 'denied' ? value : 'undecided'
  } catch {
    return 'undecided'
  }
}

function setConsent(state: 'granted' | 'denied'): void {
  try {
    window.localStorage.setItem(CONSENT_KEY, state)
  } catch {
    // storage unavailable — consent can't persist, so analytics stays off
  }
}

/**
 * Initializes PostHog by dynamically importing it (CLR-050 — the bundle
 * is only ever downloaded after consent). No-op without consent or
 * without a configured key.
 */
export function initAnalytics(): void {
  if (client || initializing || typeof window === 'undefined') return
  if (getConsent() !== 'granted') return

  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY
  if (!key) return

  initializing = true
  import('posthog-js')
    .then(({ default: posthog }) => {
      posthog.init(key, {
        api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST ?? 'https://eu.i.posthog.com',
        // Explicit events only — never DOM-scraped autocapture.
        autocapture: false,
        capture_pageview: false,
        capture_pageleave: false,
        disable_session_recording: true,
        // localStorage-only: no analytics cookies beyond the consent decision.
        persistence: 'localStorage',
      })
      client = posthog
      // Flush events that fired while the import was in flight.
      for (const item of pending) {
        client.capture(item.event, item.properties)
      }
      pending = []
    })
    .catch(() => {
      // Analytics failing to load must never affect the app.
    })
    .finally(() => {
      initializing = false
    })
}

export function grantConsent(): void {
  setConsent('granted')
  initAnalytics()
}

export function denyConsent(): void {
  setConsent('denied')
}

/**
 * Captures a whitelisted event. Silently does nothing until the user has
 * consented and PostHog is initialized.
 */
export function track(
  event: AnalyticsEvent,
  properties?: Record<string, string | number | boolean | null>
): void {
  if (client) {
    client.capture(event, properties)
    return
  }
  // Consent granted but the dynamic import is still in flight — queue.
  if (initializing) {
    pending.push({ event, properties })
  }
}
