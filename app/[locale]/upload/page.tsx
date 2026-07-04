/**
 * CLR-054 — upload → analysis flow route (/upload).
 *
 * Public: anonymous visitors get 2 lifetime free analyses (CLR-025,
 * tracked by device id + IP) — forcing sign-in here would contradict
 * that design, so the middleware exempts /upload from Clerk protection.
 */
import type { Metadata } from 'next'
import { UploadFlow } from '@/components/upload/UploadFlow'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Analyse a contract — Clairo',
    robots: { index: false, follow: false },
  }
}

export default function Page() {
  return <UploadFlow />
}
