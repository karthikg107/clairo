'use client'

/**
 * CLR-025 — Free tier lifetime quota (2 free analyses per user).
 *
 * Authenticated users are tracked server-side by their account.
 * Anonymous users are tracked by BOTH an anonymous device id
 * (localStorage, see lib/anonymousId.ts) and IP address — the backend
 * treats quota as exhausted if either signal has reached the limit.
 *
 * Usage:
 *   const { loading, allowed, remaining, refetch } = useQuota()
 *   // after a successful POST /api/v1/analyse, call refetch() (or just
 *   // use the `quota` field already included in that response directly)
 */
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { getAnonymousId } from '@/lib/anonymousId'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export interface QuotaState {
  loading: boolean
  allowed: boolean
  isFreeTier: boolean
  used: number
  limit: number
  remaining: number
  error: string | null
  refetch: () => void
}

interface QuotaApiResponse {
  allowed: boolean
  is_free_tier: boolean
  used: number
  limit: number
  remaining: number
}

const DEFAULT_QUOTA = {
  allowed: true,
  isFreeTier: true,
  used: 0,
  limit: 2,
  remaining: 2,
}

/** Attach the Clerk bearer token (if signed in) and the anonymous device id. */
export async function buildQuotaHeaders(
  getToken: () => Promise<string | null>
): Promise<Record<string, string>> {
  const token = await getToken()
  const anonymousId = getAnonymousId()

  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  if (anonymousId) headers['X-Anonymous-Id'] = anonymousId
  return headers
}

export function useQuota(): QuotaState {
  const { isLoaded, getToken } = useAuth()
  const [loading, setLoading] = useState(true)
  const [quota, setQuota] = useState(DEFAULT_QUOTA)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!isLoaded) return

    let cancelled = false

    const check = async () => {
      setLoading(true)
      setError(null)

      try {
        const headers = await buildQuotaHeaders(getToken)
        const res = await fetch(`${API_BASE}/api/v1/quota`, {
          credentials: 'include',
          headers,
        })

        if (cancelled) return
        if (!res.ok) throw new Error(`Quota check failed: ${res.status}`)

        const data: QuotaApiResponse = await res.json()
        setQuota({
          allowed: data.allowed,
          isFreeTier: data.is_free_tier,
          used: data.used,
          limit: data.limit,
          remaining: data.remaining,
        })
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error')
          // Fail-open — never block the product on a quota-check network error.
          setQuota(DEFAULT_QUOTA)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    check()
    return () => {
      cancelled = true
    }
  }, [isLoaded, getToken, tick])

  const refetch = useCallback(() => setTick((t) => t + 1), [])

  return { loading, ...quota, error, refetch }
}
