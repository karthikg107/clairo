/**
 * CLR-025 — Anonymous device identifier for free-tier lifetime quota tracking.
 *
 * Persisted in localStorage so an anonymous user's free-analysis count
 * survives page reloads and new sessions. Sent to the backend as the
 * X-Anonymous-Id header (see hooks/useQuota.ts) and combined server-side
 * with the request IP (backend/app/services/quota.py) — quota is treated
 * as exhausted if EITHER signal has reached the limit, so clearing
 * localStorage alone does not reset it.
 */
const STORAGE_KEY = 'clairo_anonymous_id'

export function getAnonymousId(): string | null {
  if (typeof window === 'undefined') return null

  try {
    const existing = window.localStorage.getItem(STORAGE_KEY)
    if (existing) return existing

    const id = crypto.randomUUID()
    window.localStorage.setItem(STORAGE_KEY, id)
    return id
  } catch {
    // localStorage unavailable (private browsing, disabled storage, etc.)
    // — the backend still has the IP signal to fall back on.
    return null
  }
}
