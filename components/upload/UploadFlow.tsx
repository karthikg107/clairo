'use client'

/**
 * CLR-054 — upload → analysis flow (wires SCR-02…SCR-08).
 *
 * Composes the already-built screens into the product's core journey:
 *
 *   upload (FileUpload / CameraCapture)
 *     → POST /upload/validate + POST /ocr
 *     → OCR review (skipped for PDF/DOCX — skip_review from the API)
 *     → language selection
 *     → POST /classify  — prohibited documents STOP here (no analyse,
 *       no quota consumption), showing ProhibitedDocumentScreen
 *     → POST /analyse
 *     → results (AnalysisResultsScreen) | quota screen (402) | error
 *
 * SECURITY: document text lives only in component state for the duration
 * of the flow — nothing is written to storage, and the state is dropped
 * on unmount/reset.
 */

import { useCallback, useState } from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useAuth } from '@clerk/nextjs'
import { Loader2, AlertTriangle } from 'lucide-react'
import { FileUpload } from './FileUpload'
import { CameraCapture } from './CameraCapture'
import { ProhibitedDocumentScreen } from './ProhibitedDocumentScreen'
import {
  OcrReview,
  type OcrPageData,
  type OcrResultData,
} from '@/components/review/OcrReview'
import {
  LanguageSelection,
  DOCUMENT_LANGUAGES,
  type LanguageSelectionValues,
} from '@/components/forms/LanguageSelection'
import { AnalysisResultsScreen } from '@/components/results'
import type { AnalysisResult } from '@/components/results/types'
import { getAnonymousId } from '@/lib/anonymousId'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ''

type Step =
  | { name: 'upload' }
  | { name: 'camera' }
  | { name: 'processing' }
  | { name: 'review'; ocr: OcrResultData }
  | { name: 'language'; text: string }
  | { name: 'analysing' }
  | {
      name: 'results'
      result: AnalysisResult
      analysisId: string | null
      isFreeTier: boolean
      values: LanguageSelectionValues
    }
  | { name: 'prohibited'; documentType: string; referral: ProhibitedReferral | null }
  | { name: 'quota' }
  | { name: 'error' }

interface ProhibitedReferral {
  org: string
  url: string
  reason_key: string
}

function languageName(code: string): string {
  return DOCUMENT_LANGUAGES.find((l) => l.code === code)?.name ?? code
}

function pagesToText(pages: OcrPageData[]): string {
  return pages
    .map((p) => p.words.map((w) => w.text).join(' '))
    .join('\n\n')
    .trim()
}

export function UploadFlow() {
  const t = useTranslations('uploadFlow')
  const { getToken, isSignedIn } = useAuth()

  const [step, setStep] = useState<Step>({ name: 'upload' })

  const apiHeaders = useCallback(
    async (json = true): Promise<Record<string, string>> => {
      const headers: Record<string, string> = {}
      if (json) headers['Content-Type'] = 'application/json'
      if (isSignedIn) {
        const token = await getToken()
        if (token) headers['Authorization'] = `Bearer ${token}`
      } else {
        const anonymousId = getAnonymousId()
        if (anonymousId) headers['X-Anonymous-Id'] = anonymousId
      }
      return headers
    },
    [getToken, isSignedIn]
  )

  // ── Step 1: file arrives (dropzone, gallery, or camera) ────────────────
  const handleFile = useCallback(
    async (file: File) => {
      setStep({ name: 'processing' })
      try {
        const headers = await apiHeaders(false)

        const validateBody = new FormData()
        validateBody.append('file', file)
        const validateRes = await fetch(`${API_BASE}/api/v1/upload/validate`, {
          method: 'POST',
          credentials: 'include',
          headers,
          body: validateBody,
        })
        const validation = await validateRes.json()
        if (!validateRes.ok || !validation.valid) {
          setStep({ name: 'error' })
          return
        }

        const ocrBody = new FormData()
        ocrBody.append('file', file)
        const ocrRes = await fetch(`${API_BASE}/api/v1/ocr`, {
          method: 'POST',
          credentials: 'include',
          headers,
          body: ocrBody,
        })
        if (!ocrRes.ok) {
          setStep({ name: 'error' })
          return
        }
        const ocr: OcrResultData = await ocrRes.json()

        if (ocr.skip_review) {
          // PDF/DOCX — extracted directly, review screen skipped by design
          setStep({ name: 'language', text: pagesToText(ocr.pages) })
        } else {
          setStep({ name: 'review', ocr })
        }
      } catch {
        setStep({ name: 'error' })
      }
    },
    [apiHeaders]
  )

  // ── Step 2: OCR review confirmed ───────────────────────────────────────
  const handleReviewConfirm = useCallback((pages: OcrPageData[]) => {
    setStep({ name: 'language', text: pagesToText(pages) })
  }, [])

  // ── Step 3: languages chosen → classify, then analyse ─────────────────
  const handleLanguageSubmit = useCallback(
    async (values: LanguageSelectionValues, text: string) => {
      setStep({ name: 'analysing' })
      try {
        const headers = await apiHeaders()

        const classifyRes = await fetch(`${API_BASE}/api/v1/classify`, {
          method: 'POST',
          credentials: 'include',
          headers,
          body: JSON.stringify({ text }),
        })
        if (!classifyRes.ok) {
          setStep({ name: 'error' })
          return
        }
        const classification = await classifyRes.json()

        if (classification.is_prohibited) {
          // Prohibited documents NEVER reach /analyse — and never cost quota.
          setStep({
            name: 'prohibited',
            documentType: classification.document_type,
            referral: classification.referral ?? null,
          })
          return
        }

        const analyseRes = await fetch(`${API_BASE}/api/v1/analyse`, {
          method: 'POST',
          credentials: 'include',
          headers,
          body: JSON.stringify({
            verified_text: text,
            doc_language: values.documentLanguage,
            country: values.country,
            output_language: values.explanationLanguage,
            document_type: classification.document_type,
          }),
        })

        if (analyseRes.status === 402) {
          setStep({ name: 'quota' })
          return
        }
        if (!analyseRes.ok) {
          setStep({ name: 'error' })
          return
        }

        const data = await analyseRes.json()
        setStep({
          name: 'results',
          result: {
            document_type: data.document_type,
            summary: data.summary,
            clauses: data.clauses,
            protective_clause_count: data.protective_clause_count,
            review_clause_count: data.review_clause_count,
          },
          analysisId: data.analysis_id ?? null,
          isFreeTier: data.quota?.is_free_tier ?? true,
          values,
        })
      } catch {
        setStep({ name: 'error' })
      }
    },
    [apiHeaders]
  )

  const reset = useCallback(() => setStep({ name: 'upload' }), [])

  // ── Render per step ────────────────────────────────────────────────────
  switch (step.name) {
    case 'upload':
      return (
        <main className="min-h-screen bg-background px-4 py-8">
          <h1 className="sr-only">{t('title')}</h1>
          <FileUpload
            onFileSelected={handleFile}
            onCameraOpen={() => setStep({ name: 'camera' })}
          />
        </main>
      )

    case 'camera':
      return <CameraCapture onCapture={handleFile} onClose={reset} />

    case 'processing':
    case 'analysing':
      return (
        <main
          className="min-h-screen bg-background flex flex-col items-center justify-center gap-3 px-4"
          aria-busy="true"
        >
          <Loader2 className="w-8 h-8 animate-spin text-brand-600" aria-hidden />
          <p role="status" className="text-sm text-neutral-600">
            {step.name === 'processing' ? t('processing') : t('analysing')}
          </p>
        </main>
      )

    case 'review':
      return (
        <OcrReview
          result={step.ocr}
          filename=""
          onConfirm={handleReviewConfirm}
          onCancel={reset}
        />
      )

    case 'language':
      return (
        <main className="min-h-screen bg-background px-4 py-8">
          <LanguageSelection
            onSubmit={(values) => handleLanguageSubmit(values, step.text)}
          />
        </main>
      )

    case 'results':
      return (
        <AnalysisResultsScreen
          result={step.result}
          docLanguageName={languageName(step.values.documentLanguage)}
          outputLanguageName={languageName(step.values.explanationLanguage)}
          analysisId={step.analysisId}
          country={step.values.country}
          isFreeTier={step.isFreeTier}
          onUpgrade={() => {
            window.location.href = '/pricing'
          }}
        />
      )

    case 'prohibited':
      return (
        <ProhibitedDocumentScreen
          documentType={step.documentType}
          referral={step.referral}
          onReset={reset}
        />
      )

    case 'quota':
      return (
        <main className="min-h-screen bg-background flex items-center justify-center px-4">
          <div className="flex flex-col items-center text-center max-w-sm">
            <h1 className="text-lg font-bold text-neutral-900">{t('quota.heading')}</h1>
            <p className="text-sm text-neutral-500 mt-2 mb-6 leading-relaxed">
              {t('quota.body')}
            </p>
            <Link
              href="/pricing"
              className="
                px-5 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
                flex items-center
                hover:bg-brand-800 transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
              "
            >
              {t('quota.cta')}
            </Link>
          </div>
        </main>
      )

    case 'error':
      return (
        <main className="min-h-screen bg-background flex items-center justify-center px-4">
          <div className="flex flex-col items-center text-center max-w-sm">
            <div className="w-14 h-14 rounded-full bg-warning-50 flex items-center justify-center mb-4">
              <AlertTriangle className="w-6 h-6 text-warning-700" aria-hidden />
            </div>
            <h1 className="text-lg font-bold text-neutral-900">{t('error.heading')}</h1>
            <p className="text-sm text-neutral-500 mt-2 mb-6 leading-relaxed">
              {t('error.body')}
            </p>
            <button
              type="button"
              onClick={reset}
              className="
                px-5 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
                hover:bg-brand-800 transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
              "
            >
              {t('error.retry')}
            </button>
          </div>
        </main>
      )
  }
}
