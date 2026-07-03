'use client'

/**
 * CLR-029 — Second step of the two-step cancellation flow.
 *
 * Step one is the "Cancel subscription" button in SubscriptionSection;
 * this dialog is the explicit confirmation. It states plainly that access
 * continues until the end of the already-paid period (no dark patterns:
 * no guilt-trip copy, cancel is one click once here, and the safe action
 * "keep subscription" is the visually primary button).
 *
 * Dialog shell (button backdrop + document-level Escape) matches
 * DeleteAccountDialog — the jsx-a11y-clean pattern, not ShareSheet.
 */

import { useEffect, useState } from 'react'
import { useTranslations, useFormatter } from 'next-intl'
import { X, Loader2 } from 'lucide-react'

interface CancelSubscriptionDialogProps {
  periodEnd: string | null
  onConfirm: () => Promise<void>
  onClose: () => void
}

export function CancelSubscriptionDialog({
  periodEnd,
  onConfirm,
  onClose,
}: CancelSubscriptionDialogProps) {
  const t = useTranslations('account.subscription.cancel_dialog')
  const format = useFormatter()
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (cancelling) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose, cancelling])

  const handleConfirm = async () => {
    if (cancelling) return
    setCancelling(true)
    setError(null)
    try {
      await onConfirm()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setCancelling(false)
    }
  }

  const body = periodEnd
    ? t('body_with_date', {
        date: format.dateTime(new Date(periodEnd), { dateStyle: 'long' }),
      })
    : t('body')

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center px-0 sm:px-4">
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        disabled={cancelling}
        onClick={onClose}
        className="absolute inset-0 bg-black/40 cursor-default disabled:cursor-not-allowed"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="cancel-subscription-heading"
        className="relative w-full sm:max-w-sm bg-white rounded-t-3xl sm:rounded-2xl shadow-xl flex flex-col max-h-[85vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2
            id="cancel-subscription-heading"
            className="text-base font-semibold text-neutral-900"
          >
            {t('heading')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={cancelling}
            aria-label={t('close')}
            className="w-8 h-8 rounded-full flex items-center justify-center text-neutral-500 hover:bg-neutral-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>

        <div className="px-5 pb-5 flex flex-col gap-4">
          <p className="text-sm text-neutral-600 leading-relaxed">{body}</p>

          {error && (
            <p className="text-xs text-danger-600" role="alert">
              {error}
            </p>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={cancelling}
              className="
                flex-1 h-11 rounded-2xl bg-brand-700 text-white text-sm font-semibold
                hover:bg-brand-800 transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
                disabled:opacity-50
              "
            >
              {t('keep')}
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={cancelling}
              className="
                flex-1 h-11 rounded-2xl border border-danger-300 text-danger-700 text-sm font-semibold
                hover:bg-danger-50 transition-colors
                flex items-center justify-center gap-2
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500
                disabled:opacity-50
              "
            >
              {cancelling && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
              {cancelling ? t('cancelling') : t('confirm_cta')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
