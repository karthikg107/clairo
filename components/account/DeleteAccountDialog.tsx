'use client'

/**
 * CLR-024 — Typed-confirmation dialog for account deletion.
 *
 * The delete button stays disabled until the user types the exact
 * confirmation word — this is a client-side affordance only; the backend
 * (POST /api/v1/account/delete) independently re-validates the same
 * confirmation string, so this check is never the only line of defense.
 *
 * Dialog shell (backdrop + role="dialog" + Escape-to-close) matches the
 * existing ShareSheet pattern (components/results/ShareSheet.tsx).
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { X, Loader2 } from 'lucide-react'

const CONFIRMATION_WORD = 'DELETE'

interface DeleteAccountDialogProps {
  onConfirm: () => Promise<void>
  onClose: () => void
}

export function DeleteAccountDialog({ onConfirm, onClose }: DeleteAccountDialogProps) {
  const t = useTranslations('account.delete_dialog')
  const [value, setValue] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Document-level Escape handling — avoids attaching key listeners to a
  // non-interactive element (jsx-a11y/no-noninteractive-element-interactions).
  useEffect(() => {
    if (deleting) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose, deleting])

  const canConfirm = value === CONFIRMATION_WORD && !deleting

  const handleConfirm = async () => {
    if (!canConfirm) return
    setDeleting(true)
    setError(null)
    try {
      await onConfirm()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setDeleting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center px-0 sm:px-4">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        disabled={deleting}
        onClick={onClose}
        className="absolute inset-0 bg-black/40 cursor-default disabled:cursor-not-allowed"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-account-heading"
        className="relative w-full sm:max-w-sm bg-white rounded-t-3xl sm:rounded-2xl shadow-xl flex flex-col max-h-[85vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2
            id="delete-account-heading"
            className="text-base font-semibold text-danger-700"
          >
            {t('heading')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={deleting}
            aria-label={t('close')}
            className="w-8 h-8 rounded-full flex items-center justify-center text-neutral-500 hover:bg-neutral-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>

        <div className="px-5 pb-5 flex flex-col gap-4">
          <p className="text-sm text-neutral-600 leading-relaxed">{t('body')}</p>

          <div>
            <label
              htmlFor="delete-confirm-input"
              className="block text-xs font-medium text-neutral-600 mb-1.5"
            >
              {t('confirm_instructions')}
            </label>
            <input
              ref={inputRef}
              id="delete-confirm-input"
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={t('confirm_placeholder')}
              aria-label={t('confirm_aria')}
              autoComplete="off"
              disabled={deleting}
              className="
                w-full h-11 px-3 rounded-xl border border-neutral-200
                text-sm text-neutral-900 placeholder:text-neutral-500
                focus:outline-none focus-visible:ring-2 focus-visible:ring-danger-500
                disabled:opacity-50
              "
            />
          </div>

          {error && (
            <p className="text-xs text-danger-600" role="alert">
              {error}
            </p>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={deleting}
              className="
                flex-1 h-11 rounded-2xl border border-neutral-200 text-sm font-medium text-neutral-700
                hover:bg-neutral-50 transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
                disabled:opacity-50
              "
            >
              {t('cancel')}
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={!canConfirm}
              className="
                flex-1 h-11 rounded-2xl bg-danger-600 text-white text-sm font-semibold
                hover:bg-danger-700 transition-colors
                flex items-center justify-center gap-2
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500 focus-visible:ring-offset-2
                disabled:opacity-40 disabled:cursor-not-allowed
              "
            >
              {deleting && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
              {deleting ? t('deleting') : t('confirm_cta')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
