/**
 * CLR-047 — catch-all for unknown paths inside the locale segment.
 *
 * Delegates straight to notFound() so the localized 404 page
 * (app/[locale]/not-found.tsx) renders instead of Next's default.
 */
import { notFound } from 'next/navigation'

export default function CatchAllPage() {
  notFound()
}
