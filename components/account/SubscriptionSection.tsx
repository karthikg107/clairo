'use client'

/**
 * CLR-029 — Subscription management section on the account settings page.
 *
 * Shows the current plan with its renewal date; a paid subscriber can
 * cancel (two-step: this section's button, then CancelSubscriptionDialog).
 * Cancellation is scheduled at period end — until then the section shows a
 * "cancels on <date>" notice with a one-click Reactivate. Billing history
 * lists Stripe invoices with downloadable PDFs (links open in a new tab,
 * hosted by Stripe — we never proxy or store invoice files).
 */

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations, useFormatter } from 'next-intl'
import { Download, ExternalLink, Loader2, RotateCcw } from 'lucide-react'
import { useSubscription } from '@/hooks/useSubscription'
import { CancelSubscriptionDialog } from './CancelSubscriptionDialog'

const PAID_TIERS = ['starter', 'pro', 'team']

export function SubscriptionSection() {
  const t = useTranslations('account.subscription')
  const tTiers = useTranslations('pricingPage.tiers')
  const format = useFormatter()
  const router = useRouter()

  const {
    loading,
    subscription,
    invoices,
    cancelSubscription,
    reactivateSubscription,
    mutating,
    mutateError,
  } = useSubscription()

  const [cancelOpen, setCancelOpen] = useState(false)

  if (loading) {
    return (
      <section className="rounded-2xl border border-neutral-200 bg-white p-5 flex justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-brand-600" aria-hidden />
      </section>
    )
  }

  if (!subscription) return null

  const isPaid = PAID_TIERS.includes(subscription.tier)
  const periodEnd = subscription.currentPeriodEnd
  const periodEndLabel = periodEnd
    ? format.dateTime(new Date(periodEnd), { dateStyle: 'long' })
    : null

  const handleReactivate = async () => {
    try {
      await reactivateSubscription()
    } catch {
      // mutateError is surfaced by the hook
    }
  }

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-neutral-900 mb-4">{t('heading')}</h2>

      <dl className="flex flex-col gap-3 text-sm mb-4">
        <div className="flex items-center justify-between">
          <dt className="text-neutral-500">{t('plan_label')}</dt>
          <dd className="text-neutral-900 font-medium">
            {tTiers(`${subscription.tier}.name`, { fallback: subscription.tier })}
          </dd>
        </div>
        {isPaid && periodEndLabel && !subscription.cancelAtPeriodEnd && (
          <div className="flex items-center justify-between">
            <dt className="text-neutral-500">{t('renews_label')}</dt>
            <dd className="text-neutral-900 font-medium">{periodEndLabel}</dd>
          </div>
        )}
      </dl>

      {subscription.cancelAtPeriodEnd && (
        <div className="rounded-xl bg-warning-50 border border-warning-200 p-3 mb-4">
          <p className="text-xs text-warning-800 leading-relaxed">
            {periodEndLabel
              ? t('pending_cancellation_with_date', { date: periodEndLabel })
              : t('pending_cancellation')}
          </p>
          <button
            type="button"
            onClick={handleReactivate}
            disabled={mutating}
            className="
              mt-2 px-3 h-9 rounded-xl bg-brand-700 text-white text-xs font-semibold
              hover:bg-brand-800 transition-colors
              flex items-center gap-1.5
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
              disabled:opacity-50
            "
          >
            {mutating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
            ) : (
              <RotateCcw className="w-3.5 h-3.5" aria-hidden />
            )}
            {t('reactivate_cta')}
          </button>
        </div>
      )}

      {mutateError && (
        <p className="text-xs text-danger-600 mb-3" role="alert">
          {mutateError}
        </p>
      )}

      {!isPaid ? (
        <button
          type="button"
          onClick={() => router.push('/pricing')}
          className="
            px-4 h-10 rounded-2xl bg-brand-700 text-white text-sm font-semibold
            hover:bg-brand-800 transition-colors
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
          "
        >
          {t('view_plans_cta')}
        </button>
      ) : (
        !subscription.cancelAtPeriodEnd && (
          <button
            type="button"
            onClick={() => setCancelOpen(true)}
            className="
              px-4 h-10 rounded-2xl border border-neutral-200 text-sm font-medium text-neutral-700
              hover:bg-neutral-50 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
            "
          >
            {t('cancel_cta')}
          </button>
        )
      )}

      {invoices.length > 0 && (
        <div className="mt-5 pt-4 border-t border-neutral-100">
          <h3 className="text-xs font-semibold text-neutral-900 mb-3">
            {t('billing_history.heading')}
          </h3>
          <ul className="flex flex-col gap-2">
            {invoices.map((invoice) => (
              <li
                key={invoice.id}
                className="flex items-center justify-between gap-3 text-xs"
              >
                <span className="text-neutral-600 shrink-0">
                  {format.dateTime(new Date(invoice.createdAt), {
                    dateStyle: 'medium',
                  })}
                </span>
                <span className="text-neutral-900 font-medium">
                  {invoice.amountPaid} {invoice.currency}
                </span>
                <span className="flex-1 text-neutral-500 truncate">
                  {t(`billing_history.status.${invoice.status}`, {
                    fallback: invoice.status,
                  })}
                </span>
                {invoice.invoicePdf ? (
                  <a
                    href={invoice.invoicePdf}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={t('billing_history.download_aria', {
                      date: format.dateTime(new Date(invoice.createdAt), {
                        dateStyle: 'medium',
                      }),
                    })}
                    className="
                      shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-brand-700
                      hover:bg-brand-50 transition-colors
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
                    "
                  >
                    <Download className="w-4 h-4" aria-hidden />
                  </a>
                ) : invoice.hostedInvoiceUrl ? (
                  <a
                    href={invoice.hostedInvoiceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={t('billing_history.view_aria', {
                      date: format.dateTime(new Date(invoice.createdAt), {
                        dateStyle: 'medium',
                      }),
                    })}
                    className="
                      shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-brand-700
                      hover:bg-brand-50 transition-colors
                      focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
                    "
                  >
                    <ExternalLink className="w-4 h-4" aria-hidden />
                  </a>
                ) : (
                  <span className="shrink-0 w-8" aria-hidden />
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {cancelOpen && (
        <CancelSubscriptionDialog
          periodEnd={periodEnd}
          onConfirm={cancelSubscription}
          onClose={() => setCancelOpen(false)}
        />
      )}
    </section>
  )
}
