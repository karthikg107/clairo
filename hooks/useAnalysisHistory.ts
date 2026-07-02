'use client'

/**
 * CLR-023 — Analysis history for the dashboard.
 *
 * Fetches the full list once (GET /api/v1/analyses) — search and filter
 * chips operate client-side on the returned list, see
 * components/dashboard/DashboardPage.tsx. History size for this product
 * is small enough that this is simpler than a server-side search API.
 */
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export interface AnalysisHistoryItem {
  id: string
  documentType: string
  docLanguage: string
  outputLanguage: string
  summary: string
  createdAt: string
}

interface AnalysisHistoryApiItem {
  id: string
  document_type: string
  doc_language: string
  output_language: string
  summary: string
  created_at: string
}

interface AnalysisHistoryApiResponse {
  items: AnalysisHistoryApiItem[]
  total: number
}

export interface AnalysisHistoryState {
  loading: boolean
  items: AnalysisHistoryItem[]
  error: string | null
  refetch: () => void
}

export function useAnalysisHistory(): AnalysisHistoryState {
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState<AnalysisHistoryItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!isLoaded) return
    if (!isSignedIn) {
      setLoading(false)
      setItems([])
      return
    }

    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)

      try {
        const token = await getToken()
        const res = await fetch(`${API_BASE}/api/v1/analyses`, {
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        })

        if (cancelled) return
        if (!res.ok) throw new Error(`Failed to load history: ${res.status}`)

        const data: AnalysisHistoryApiResponse = await res.json()
        setItems(
          data.items.map((item) => ({
            id: item.id,
            documentType: item.document_type,
            docLanguage: item.doc_language,
            outputLanguage: item.output_language,
            summary: item.summary,
            createdAt: item.created_at,
          }))
        )
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error')
          setItems([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [isLoaded, isSignedIn, getToken, tick])

  const refetch = useCallback(() => setTick((t) => t + 1), [])

  return { loading, items, error, refetch }
}
