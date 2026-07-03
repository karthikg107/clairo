'use client'

/**
 * CLR-047 — last-resort error boundary (root layout crashed).
 *
 * Fires only when the locale layout itself fails, BEFORE i18n messages
 * can load — so this one page is static English by necessity; every
 * normal error renders the translated app/[locale]/error.tsx instead.
 * Must render its own <html>/<body> per Next's global-error contract.
 * No technical details shown.
 */

export default function GlobalError({
  error: _error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'system-ui, sans-serif',
          background: '#F8FAFC',
          color: '#171717',
          textAlign: 'center',
          padding: '1rem',
        }}
      >
        <div style={{ maxWidth: '24rem' }}>
          <h1 style={{ fontSize: '1.125rem', fontWeight: 700 }}>
            Sorry — something went wrong
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#525252', lineHeight: 1.6 }}>
            Your document was not stored — Clairo never keeps document content, including
            when errors happen.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: '1rem',
              padding: '0.6rem 1.25rem',
              borderRadius: '1rem',
              border: 'none',
              background: '#103065',
              color: '#fff',
              fontWeight: 600,
              fontSize: '0.875rem',
              cursor: 'pointer',
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  )
}
