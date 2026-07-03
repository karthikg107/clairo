'use client'

/**
 * CLR-041 — Share link generation for an analysis.
 *
 * createShareLink() POSTs to /api/v1/share-links and returns the full
 * shareable URL (current origin + /s/[uuid] — clairo.app/s/[uuid] in
 * production). The backend reuses an existing active link for the same
 * analysis, so repeated taps on Share never mint duplicate URLs.
 */
import { useState, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export interface ShareLinkInfo {
  shareId: string
  shareUrl: string
  expiresAt: string
}

export interface ShareLinkState {
  shareLink: ShareLinkInfo | null
  creating: boolean
  error: string | null
  createShareLink: (analysisId: string) => Promise<ShareLinkInfo>
  revokeShareLink: (shareId: string) => Promise<void>
}

export function useShareLink(): ShareLinkState {
  const { getToken } = useAuth()
  const [shareLink, setShareLink] = useState<ShareLinkInfo | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [getToken])

  const createShareLink = useCallback(
    async (analysisId: string): Promise<ShareLinkInfo> => {
      setCreating(true)
      setError(null)
      try {
        const headers = await authHeaders()
        const res = await fetch(`${API_BASE}/api/v1/share-links`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', ...headers },
          body: JSON.stringify({ analysis_id: analysisId }),
        })
        if (!res.ok) throw new Error(`Failed to create share link: ${res.status}`)

        const data: { share_id: string; share_path: string; expires_at: string } =
          await res.json()
        const info: ShareLinkInfo = {
          shareId: data.share_id,
          shareUrl: `${window.location.origin}${data.share_path}`,
          expiresAt: data.expires_at,
        }
        setShareLink(info)
        return info
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        throw err
      } finally {
        setCreating(false)
      }
    },
    [authHeaders]
  )

  const revokeShareLink = useCallback(
    async (shareId: string): Promise<void> => {
      const headers = await authHeaders()
      const res = await fetch(`${API_BASE}/api/v1/share-links/${shareId}/revoke`, {
        method: 'POST',
        credentials: 'include',
        headers,
      })
      if (!res.ok) throw new Error(`Failed to revoke share link: ${res.status}`)
      setShareLink((current) => (current?.shareId === shareId ? null : current))
    },
    [authHeaders]
  )

  return { shareLink, creating, error, createShareLink, revokeShareLink }
}
