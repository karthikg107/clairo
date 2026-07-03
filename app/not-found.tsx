/**
 * CLR-051 — root 404 for paths that never resolve a locale (the localized
 * version at app/[locale]/not-found.tsx handles everything else).
 *
 * Must render its own <html> with lang + title — without this file, Next
 * serves a bare error shell that fails WCAG (no title, no lang).
 * Static English by necessity: no locale context exists out here.
 */
import Link from 'next/link'

export const metadata = { title: 'Page not found — Clairo' }

export default function RootNotFound() {
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
        <main style={{ maxWidth: '24rem' }}>
          <h1 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Page not found</h1>
          <p style={{ fontSize: '0.875rem', color: '#525252', lineHeight: 1.6 }}>
            That page doesn&apos;t exist — maybe the link was mistyped or has moved.
          </p>
          <p style={{ marginTop: '1rem' }}>
            <Link
              href="/"
              style={{ color: '#103065', fontWeight: 600, fontSize: '0.875rem' }}
            >
              Go to the homepage
            </Link>
          </p>
        </main>
      </body>
    </html>
  )
}
