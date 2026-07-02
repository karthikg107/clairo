'use client'

/**
 * CLR-024 — Account settings: profile fetch, language-preference update,
 * GDPR data export, and account deletion.
 */
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export interface AccountInfo {
  email: string
  subscriptionTier: string
  memberSince: string
  docLanguage: string | null
  outputLanguage: string | null
  country: string | null
}

interface AccountApiResponse {
  email: string
  subscription_tier: string
  member_since: string
  doc_language: string | null
  output_language: string | null
  country: string | null
}

function fromApi(data: AccountApiResponse): AccountInfo {
  return {
    email: data.email,
    subscriptionTier: data.subscription_tier,
    memberSince: data.member_since,
    docLanguage: data.doc_language,
    outputLanguage: data.output_language,
    country: data.country,
  }
}

export interface AccountSettingsState {
  loading: boolean
  account: AccountInfo | null
  error: string | null
  refetch: () => void
  saveLanguagePreferences: (values: {
    docLanguage: string
    outputLanguage: string
    country: string
  }) => Promise<void>
  saving: boolean
  saveError: string | null
  exportData: () => Promise<unknown>
  deleteAccount: (confirmation: string) => Promise<void>
}

export function useAccountSettings(): AccountSettingsState {
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const [loading, setLoading] = useState(true)
  const [account, setAccount] = useState<AccountInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [getToken])

  useEffect(() => {
    if (!isLoaded) return
    if (!isSignedIn) {
      setLoading(false)
      setAccount(null)
      return
    }

    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)

      try {
        const headers = await authHeaders()
        const res = await fetch(`${API_BASE}/api/v1/account`, {
          credentials: 'include',
          headers,
        })

        if (cancelled) return
        if (!res.ok) throw new Error(`Failed to load account: ${res.status}`)

        const data: AccountApiResponse = await res.json()
        setAccount(fromApi(data))
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [isLoaded, isSignedIn, authHeaders, tick])

  const refetch = useCallback(() => setTick((t) => t + 1), [])

  const saveLanguagePreferences = useCallback(
    async (values: { docLanguage: string; outputLanguage: string; country: string }) => {
      setSaving(true)
      setSaveError(null)

      try {
        const headers = await authHeaders()
        const res = await fetch(`${API_BASE}/api/v1/account/language-preferences`, {
          method: 'PATCH',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', ...headers },
          body: JSON.stringify({
            doc_language: values.docLanguage,
            output_language: values.outputLanguage,
            country: values.country,
          }),
        })

        if (!res.ok) throw new Error(`Failed to save preferences: ${res.status}`)

        const data: AccountApiResponse = await res.json()
        setAccount(fromApi(data))
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : 'Unknown error')
        throw err
      } finally {
        setSaving(false)
      }
    },
    [authHeaders]
  )

  const exportData = useCallback(async () => {
    const headers = await authHeaders()
    const res = await fetch(`${API_BASE}/api/v1/account/export`, {
      credentials: 'include',
      headers,
    })
    if (!res.ok) throw new Error(`Failed to export data: ${res.status}`)
    return res.json()
  }, [authHeaders])

  const deleteAccount = useCallback(
    async (confirmation: string) => {
      const headers = await authHeaders()
      const res = await fetch(`${API_BASE}/api/v1/account/delete`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...headers },
        body: JSON.stringify({ confirmation }),
      })
      if (!res.ok) throw new Error(`Failed to delete account: ${res.status}`)
    },
    [authHeaders]
  )

  return {
    loading,
    account,
    error,
    refetch,
    saveLanguagePreferences,
    saving,
    saveError,
    exportData,
    deleteAccount,
  }
}
