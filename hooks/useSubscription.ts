'use client'

/**
 * CLR-029 — Subscription management: current plan + renewal date,
 * cancel at period end, reactivate, and billing history (invoices).
 */
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

export interface SubscriptionInfo {
  tier: string
  status: string
  billingInterval: string | null
  currentPeriodEnd: string | null
  cancelAtPeriodEnd: boolean
}

interface SubscriptionApiResponse {
  tier: string
  status: string
  billing_interval: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
}

function subscriptionFromApi(data: SubscriptionApiResponse): SubscriptionInfo {
  return {
    tier: data.tier,
    status: data.status,
    billingInterval: data.billing_interval,
    currentPeriodEnd: data.current_period_end,
    cancelAtPeriodEnd: data.cancel_at_period_end,
  }
}

export interface InvoiceInfo {
  id: string
  status: string
  amountPaid: string
  currency: string
  createdAt: string
  hostedInvoiceUrl: string | null
  invoicePdf: string | null
}

interface InvoiceApiResponse {
  id: string
  status: string
  amount_paid: string
  currency: string
  created_at: string
  hosted_invoice_url: string | null
  invoice_pdf: string | null
}

function invoiceFromApi(data: InvoiceApiResponse): InvoiceInfo {
  return {
    id: data.id,
    status: data.status,
    amountPaid: data.amount_paid,
    currency: data.currency,
    createdAt: data.created_at,
    hostedInvoiceUrl: data.hosted_invoice_url,
    invoicePdf: data.invoice_pdf,
  }
}

export interface SubscriptionState {
  loading: boolean
  subscription: SubscriptionInfo | null
  invoices: InvoiceInfo[]
  error: string | null
  cancelSubscription: () => Promise<void>
  reactivateSubscription: () => Promise<void>
  mutating: boolean
  mutateError: string | null
}

export function useSubscription(): SubscriptionState {
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const [loading, setLoading] = useState(true)
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null)
  const [invoices, setInvoices] = useState<InvoiceInfo[]>([])
  const [error, setError] = useState<string | null>(null)
  const [mutating, setMutating] = useState(false)
  const [mutateError, setMutateError] = useState<string | null>(null)

  const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [getToken])

  useEffect(() => {
    if (!isLoaded) return
    if (!isSignedIn) {
      setLoading(false)
      setSubscription(null)
      return
    }

    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)

      try {
        const headers = await authHeaders()
        const [subRes, invRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/billing/subscription`, {
            credentials: 'include',
            headers,
          }),
          fetch(`${API_BASE}/api/v1/billing/invoices`, {
            credentials: 'include',
            headers,
          }),
        ])

        if (cancelled) return
        if (!subRes.ok) throw new Error(`Failed to load subscription: ${subRes.status}`)

        const subData: SubscriptionApiResponse = await subRes.json()
        setSubscription(subscriptionFromApi(subData))

        // Billing history is non-critical — a failure here shouldn't hide
        // the plan/cancel controls, so it degrades to an empty list.
        if (invRes.ok) {
          const invData: InvoiceApiResponse[] = await invRes.json()
          if (!cancelled) setInvoices(invData.map(invoiceFromApi))
        }
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
  }, [isLoaded, isSignedIn, authHeaders])

  const mutate = useCallback(
    async (path: 'cancel' | 'reactivate') => {
      setMutating(true)
      setMutateError(null)
      try {
        const headers = await authHeaders()
        const res = await fetch(`${API_BASE}/api/v1/billing/${path}`, {
          method: 'POST',
          credentials: 'include',
          headers,
        })
        if (!res.ok) throw new Error(`Request failed: ${res.status}`)

        const data: SubscriptionApiResponse = await res.json()
        setSubscription(subscriptionFromApi(data))
      } catch (err) {
        setMutateError(err instanceof Error ? err.message : 'Unknown error')
        throw err
      } finally {
        setMutating(false)
      }
    },
    [authHeaders]
  )

  const cancelSubscription = useCallback(() => mutate('cancel'), [mutate])
  const reactivateSubscription = useCallback(() => mutate('reactivate'), [mutate])

  return {
    loading,
    subscription,
    invoices,
    error,
    cancelSubscription,
    reactivateSubscription,
    mutating,
    mutateError,
  }
}
