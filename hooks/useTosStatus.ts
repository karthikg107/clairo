'use client'

/**
 * CLR-022 — Hook to check whether the current user has accepted the TOS.
 *
 * Usage:
 *   const { needsTos, loading } = useTosStatus()
 *   if (needsTos) return <TrustScreen onAccepted={refetch} />
 */
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

interface TosStatus {
  loading: boolean
  needsTos: boolean
  error: string | null
  refetch: () => void
}

export function useTosStatus(): TosStatus {
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const [loading, setLoading] = useState(true)
  const [needsTos, setNeedsTos] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!isLoaded) return
    if (!isSignedIn) {
      // Unauthenticated — no TOS check needed (will redirect to sign-in)
      setLoading(false)
      setNeedsTos(false)
      return
    }

    let cancelled = false

    const check = async () => {
      setLoading(true)
      setError(null)

      try {
        const token = await getToken()
        const res = await fetch(`${API_BASE}/api/v1/consent`, {
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })

        if (cancelled) return

        if (!res.ok) {
          throw new Error(`Consent check failed: ${res.status}`)
        }

        const data: { has_accepted: boolean } = await res.json()
        setNeedsTos(!data.has_accepted)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error')
          // Fail-open for network errors so users aren't permanently locked out
          setNeedsTos(false)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    check()
    return () => { cancelled = true }
  }, [isLoaded, isSignedIn, getToken, tick])

  const refetch = useCallback(() => setTick((t) => t + 1), [])

  return { loading, needsTos, error, refetch }
}
