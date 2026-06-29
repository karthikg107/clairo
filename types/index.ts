// ─── Locale ──────────────────────────────────────────────────────────────────
export type { Locale } from '@/middleware'
export { locales, rtlLocales } from '@/middleware'

// ─── Document ────────────────────────────────────────────────────────────────
export type DocumentType =
  | 'rental'
  | 'employment'
  | 'freelance'
  | 'tos'
  | 'other_permitted'
  | 'prohibited'

export type ProhibitedDocumentType =
  | 'court_order'
  | 'immigration'
  | 'medical_consent'
  | 'financial_instrument'
  | 'minor_involved'

// ─── Analysis ────────────────────────────────────────────────────────────────
export type FlagType = 'protects_user' | 'less_common' | 'standard'

export interface ClauseFlag {
  type: FlagType
  label: string
}

export interface Clause {
  id: string
  title: string
  explanation: string
  sourceText: string
  flag: ClauseFlag
  frequencyPercent: number
}

export interface AnalysisResult {
  id: string
  documentType: DocumentType
  docLanguage: string
  outputLanguage: string
  country: string
  summary: string
  clauses: Clause[]
  analyzedAt: string
  cached: boolean
}

// ─── User ─────────────────────────────────────────────────────────────────────
export type SubscriptionTier = 'free' | 'starter' | 'pro' | 'team'

export interface User {
  id: string
  emailHash: string
  createdAt: string
  subscriptionTier: SubscriptionTier
  analysisCount: number
  languagePreferences?: {
    docLanguage?: string
    country?: string
    outputLanguage?: string
  }
}

// ─── Upload ───────────────────────────────────────────────────────────────────
export type AcceptedMimeType =
  | 'application/pdf'
  | 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  | 'image/jpeg'
  | 'image/png'
  | 'image/heic'

export const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024 // 25 MB

export interface UploadedFile {
  name: string
  size: number
  type: AcceptedMimeType
  dataUrl?: string // client-side preview only — never sent to server as-is
}

// ─── API responses ────────────────────────────────────────────────────────────
export interface ApiError {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface ApiResponse<T> {
  data?: T
  error?: ApiError
  requestId: string
}
