'use client'

/**
 * CLR-018 — Share sheet for the analysis results screen.
 *
 * WhatsApp is the primary share channel (highest-intent target audience).
 * Falls back to the Web Share API where available, with copy-link always present.
 *
 * Scope note: this is the share UI only. Shareable link generation (CLR-041)
 * and the public shared-analysis page (CLR-042) are separate tickets — this
 * component accepts a pre-built `shareUrl` and does not generate one itself.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import { X, Copy, Check, Share2 } from 'lucide-react'

interface ShareSheetProps {
  shareUrl: string
  documentType: string
  onClose: () => void
}

function WhatsAppIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
      <path d="M12.012 2c-5.506 0-9.988 4.482-9.988 9.988 0 1.762.464 3.484 1.345 5.002L2 22l5.146-1.348a9.954 9.954 0 0 0 4.866 1.24h.004c5.505 0 9.987-4.483 9.987-9.989C21.999 6.482 17.517 2 12.012 2zm0 18.158h-.003a8.16 8.16 0 0 1-4.158-1.14l-.298-.177-3.054.8.815-2.977-.194-.306a8.146 8.146 0 0 1-1.255-4.37c0-4.503 3.665-8.168 8.17-8.168 2.182 0 4.234.85 5.777 2.394a8.115 8.115 0 0 1 2.39 5.78c0 4.504-3.665 8.164-8.19 8.164z" />
    </svg>
  )
}

export function ShareSheet({ shareUrl, documentType, onClose }: ShareSheetProps) {
  const t = useTranslations('results.share')
  const [copied, setCopied] = useState(false)
  const closeBtnRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    closeBtnRef.current?.focus()
  }, [])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose]
  )

  const message = t('whatsapp_message', { type: documentType, url: shareUrl })

  const handleWhatsApp = () => {
    window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, '_blank', 'noopener,noreferrer')
  }

  const handleNativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: t('share_title'), text: message, url: shareUrl })
      } catch {
        // user cancelled — no-op
      }
    }
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(shareUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center px-0 sm:px-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-sheet-heading"
        onKeyDown={handleKeyDown}
        className="w-full sm:max-w-sm bg-white rounded-t-3xl sm:rounded-2xl shadow-xl flex flex-col max-h-[85vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <h2 id="share-sheet-heading" className="text-base font-semibold text-neutral-900">
            {t('heading')}
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label={t('close')}
            className="w-8 h-8 rounded-full flex items-center justify-center text-neutral-500 hover:bg-neutral-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>

        <div className="px-5 pb-5 flex flex-col gap-2">
          {/* WhatsApp — primary share option */}
          <button
            type="button"
            onClick={handleWhatsApp}
            className="
              flex items-center gap-3 w-full min-h-touch px-4 rounded-2xl
              bg-[#25D366] text-white font-medium text-sm
              hover:brightness-95 transition
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#25D366]
            "
          >
            <WhatsAppIcon className="w-5 h-5 shrink-0" />
            {t('whatsapp')}
          </button>

          {typeof navigator !== 'undefined' && 'share' in navigator && (
            <button
              type="button"
              onClick={handleNativeShare}
              className="
                flex items-center gap-3 w-full min-h-touch px-4 rounded-2xl
                border border-neutral-200 text-neutral-700 font-medium text-sm
                hover:bg-neutral-50 transition
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
              "
            >
              <Share2 className="w-5 h-5 shrink-0" aria-hidden />
              {t('more_options')}
            </button>
          )}

          <button
            type="button"
            onClick={handleCopy}
            className="
              flex items-center gap-3 w-full min-h-touch px-4 rounded-2xl
              border border-neutral-200 text-neutral-700 font-medium text-sm
              hover:bg-neutral-50 transition
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
            "
          >
            {copied ? (
              <Check className="w-5 h-5 shrink-0 text-success-600" aria-hidden />
            ) : (
              <Copy className="w-5 h-5 shrink-0" aria-hidden />
            )}
            {copied ? t('copied') : t('copy_link')}
          </button>
        </div>
      </div>
    </div>
  )
}
