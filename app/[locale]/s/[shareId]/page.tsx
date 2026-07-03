/**
 * CLR-042 — Public shared-analysis page (/s/[shareId]).
 *
 * Public — exempted from Clerk auth in middleware.ts. Server component:
 * the payload is fetched server-side so Open Graph tags render for
 * WhatsApp/Twitter link previews (crawlers don't execute JS).
 *
 * noindex on EVERY response — shared analyses must never appear in
 * search engines, whether the link is live or not.
 *
 * Expired, revoked, and unknown links all render the same friendly
 * "no longer available" view (the API already returns identical 404s
 * for all three — CLR-041 anti-enumeration).
 */
import type { Metadata } from 'next'
import { cache } from 'react'
import { getTranslations } from 'next-intl/server'
import {
  SharedAnalysisView,
  type SharedAnalysisPayload,
} from '@/components/shared/SharedAnalysisView'
import { SharedLinkUnavailable } from '@/components/shared/SharedLinkUnavailable'

const API_BASE =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// react cache() → one API call (and one rate-limit view count) per request,
// shared between generateMetadata and the page render.
const fetchSharedAnalysis = cache(
  async (shareId: string): Promise<SharedAnalysisPayload | null> => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/shared/${shareId}`, {
        cache: 'no-store',
      })
      if (!res.ok) return null
      return (await res.json()) as SharedAnalysisPayload
    } catch {
      return null
    }
  }
)

interface PageProps {
  params: { locale: string; shareId: string }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const t = await getTranslations({ locale: params.locale, namespace: 'sharedPage' })
  const tTypes = await getTranslations({
    locale: params.locale,
    namespace: 'results.document_types',
  })
  const payload = await fetchSharedAnalysis(params.shareId)

  // noindex unconditionally — live or dead, shared pages stay out of search.
  const robots = { index: false, follow: false }

  if (!payload) {
    return { title: t('unavailable.heading'), robots }
  }

  // document_type is one of the 5 permitted-type enum values, all present
  // in every locale's results.document_types section (CLR-023).
  const typeName = tTypes(payload.document_type)
  const title = t('og_title', { type: typeName })
  // Summary is AI-generated plain language from the sanitized payload —
  // safe by construction (never document text). Truncated for OG limits.
  const description =
    payload.summary.length > 200 ? `${payload.summary.slice(0, 197)}…` : payload.summary

  return {
    title: `${title} — Clairo`,
    description,
    robots,
    openGraph: {
      title,
      description,
      siteName: 'Clairo',
      type: 'article',
    },
    twitter: {
      card: 'summary',
      title,
      description,
    },
  }
}

export default async function Page({ params }: PageProps) {
  const payload = await fetchSharedAnalysis(params.shareId)

  if (!payload) {
    return <SharedLinkUnavailable />
  }

  return <SharedAnalysisView payload={payload} />
}
