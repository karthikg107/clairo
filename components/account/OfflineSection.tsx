'use client'

/**
 * CLR-048 — offline cache controls on the account settings page.
 *
 * The service worker keeps the 10 most recent analyses available
 * offline (public/sw.js). This section lets the user wipe that cache
 * — both via a message to the active service worker and directly
 * through the Cache Storage API (covers the no-active-SW case).
 */

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { WifiOff, Check, Loader2 } from 'lucide-react'

const CACHE_NAME = 'clairo-analyses-v1'

export function OfflineSection() {
  const t = useTranslations('account.offline')
  const [clearing, setClearing] = useState(false)
  const [cleared, setCleared] = useState(false)

  const handleClear = async () => {
    setClearing(true)
    try {
      if ('caches' in window) {
        await window.caches.delete(CACHE_NAME)
      }
      navigator.serviceWorker?.controller?.postMessage({
        type: 'CLEAR_ANALYSES_CACHE',
      })
      setCleared(true)
      setTimeout(() => setCleared(false), 3000)
    } catch {
      // Cache API unavailable — nothing cached to clear anyway.
    } finally {
      setClearing(false)
    }
  }

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-5">
      <div className="flex items-center gap-2 mb-1">
        <WifiOff className="w-4 h-4 text-brand-700" aria-hidden />
        <h2 className="text-sm font-semibold text-neutral-900">{t('heading')}</h2>
      </div>
      <p className="text-xs text-neutral-500 mb-3 leading-relaxed">{t('body')}</p>
      <button
        type="button"
        onClick={handleClear}
        disabled={clearing}
        className="
          px-4 h-10 rounded-2xl border border-neutral-200 text-sm font-medium text-neutral-700
          hover:bg-neutral-50 transition-colors
          flex items-center gap-2
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
          disabled:opacity-50
        "
      >
        {clearing ? (
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
        ) : cleared ? (
          <Check className="w-4 h-4 text-success-600" aria-hidden />
        ) : null}
        {cleared ? t('cleared') : t('clear_cta')}
      </button>
    </section>
  )
}
