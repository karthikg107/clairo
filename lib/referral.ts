/**
 * CLR-044 — client-side referrer handoff.
 *
 * /ref/[userId] stores the referrer id here; after sign-up,
 * ReferralClaimer reads it, claims the referral, and clears it.
 * localStorage (not a cookie) — it never needs to reach the server on
 * page requests, only in the explicit claim call.
 */

const STORAGE_KEY = 'clairo_referrer'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function storeReferrer(userId: string): void {
  if (!UUID_RE.test(userId)) return
  try {
    window.localStorage.setItem(STORAGE_KEY, userId)
  } catch {
    // storage unavailable (private mode) — referral simply won't be credited
  }
}

export function readReferrer(): string | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value && UUID_RE.test(value) ? value : null
  } catch {
    return null
  }
}

export function clearReferrer(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // no-op
  }
}
