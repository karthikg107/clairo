import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'Clairo — Understand any contract. In any language. Instantly.',
    template: '%s | Clairo',
  },
  description:
    'Clairo explains what your contract says in plain language. Not legal advice — clear understanding.',
  metadataBase: new URL('https://clairo.app'),
  robots: { index: true, follow: true },
  // CLR-048/051 — the actual manifest file (was /manifest.json, which
  // doesn't exist)
  manifest: '/manifest.webmanifest',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#103065', // brand-700, matches the manifest
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return children
}
