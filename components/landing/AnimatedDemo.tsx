/**
 * CLR-046 — animated hero demo.
 *
 * Pure CSS/SVG: a stylized document gets "scanned" and plain-language
 * explanation chips appear. Loops forever (8s), no video, no sound, no
 * JavaScript. Decorative only (aria-hidden) — the value proposition is
 * carried by the hero copy, not this illustration. Respects
 * prefers-reduced-motion (chips shown statically, no scanline).
 */

import { ShieldCheck, AlertTriangle } from 'lucide-react'

export function AnimatedDemo({
  protectiveLabel,
  reviewLabel,
  plainLabel,
}: {
  protectiveLabel: string
  reviewLabel: string
  plainLabel: string
}) {
  return (
    <div aria-hidden="true" className="relative mx-auto w-full max-w-[300px] select-none">
      {/* Document card */}
      <div className="relative overflow-hidden rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
        {/* "Legalese" skeleton lines */}
        <div className="flex flex-col gap-2.5">
          <div className="h-2.5 w-3/4 rounded-full bg-neutral-200" />
          <div className="h-2.5 w-full rounded-full bg-neutral-200" />
          <div className="h-2.5 w-5/6 rounded-full bg-neutral-200" />
          <div className="h-2.5 w-full rounded-full bg-neutral-200" />
          <div className="h-2.5 w-2/3 rounded-full bg-neutral-200" />
        </div>

        {/* Scanline sweeping down the document */}
        <div className="landing-scanline pointer-events-none absolute inset-x-3 top-4 h-7 rounded-lg bg-brand-500/15 ring-1 ring-brand-500/30" />

        {/* Explanation chips fading in */}
        <div className="mt-4 flex flex-col gap-2">
          <span className="landing-chip inline-flex w-fit items-center gap-1.5 rounded-full bg-success-50 px-3 py-1.5 text-xs font-medium text-success-700">
            <ShieldCheck className="h-3.5 w-3.5" />
            {protectiveLabel}
          </span>
          <span className="landing-chip landing-chip-delay-1 inline-flex w-fit items-center gap-1.5 rounded-full bg-warning-50 px-3 py-1.5 text-xs font-medium text-warning-700">
            <AlertTriangle className="h-3.5 w-3.5" />
            {reviewLabel}
          </span>
          <span className="landing-chip landing-chip-delay-2 inline-flex w-fit items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700">
            {plainLabel}
          </span>
        </div>
      </div>
    </div>
  )
}
