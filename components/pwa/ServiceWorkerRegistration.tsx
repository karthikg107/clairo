'use client'

/**
 * CLR-048 — PWA lifecycle, mounted once in the locale layout.
 *
 * - Registers /sw.js (offline cache for analyses — see public/sw.js).
 * - Counts distinct visits (localStorage counter, incremented at most
 *   once per browser session) and shows the install prompt banner once
 *   the user has visited 3+ times, the browser offers
 *   beforeinstallprompt, and the user hasn't dismissed it before.
 */

import { useEffect, useState } from 'react'
import { InstallPrompt } from './InstallPrompt'

const VISITS_KEY = 'clairo_visits'
const SESSION_COUNTED_KEY = 'clairo_visit_counted'
const INSTALL_DISMISSED_KEY = 'clairo_install_dismissed'
const INSTALL_PROMPT_MIN_VISITS = 3

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

function countVisit(): number {
  try {
    const visits = parseInt(window.localStorage.getItem(VISITS_KEY) ?? '0', 10) || 0
    if (window.sessionStorage.getItem(SESSION_COUNTED_KEY)) return visits
    window.sessionStorage.setItem(SESSION_COUNTED_KEY, '1')
    const next = visits + 1
    window.localStorage.setItem(VISITS_KEY, String(next))
    return next
  } catch {
    return 0
  }
}

export function ServiceWorkerRegistration() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null)
  const [showInstall, setShowInstall] = useState(false)

  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // Registration failure just means no offline cache — never fatal.
      })
    }

    const visits = countVisit()

    const onBeforeInstall = (e: Event) => {
      e.preventDefault()
      let dismissed = false
      try {
        dismissed = window.localStorage.getItem(INSTALL_DISMISSED_KEY) === '1'
      } catch {
        // storage unavailable — treat as not dismissed
      }
      if (visits >= INSTALL_PROMPT_MIN_VISITS && !dismissed) {
        setInstallEvent(e as BeforeInstallPromptEvent)
        setShowInstall(true)
      }
    }

    window.addEventListener('beforeinstallprompt', onBeforeInstall)
    return () => window.removeEventListener('beforeinstallprompt', onBeforeInstall)
  }, [])

  const handleInstall = async () => {
    if (!installEvent) return
    setShowInstall(false)
    await installEvent.prompt()
    // Either outcome — don't nag again this install cycle.
    setInstallEvent(null)
  }

  const handleDismiss = () => {
    setShowInstall(false)
    try {
      window.localStorage.setItem(INSTALL_DISMISSED_KEY, '1')
    } catch {
      // no-op
    }
  }

  if (!showInstall) return null
  return <InstallPrompt onInstall={handleInstall} onDismiss={handleDismiss} />
}
