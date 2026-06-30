/**
 * CLR-039 — Terms of Service page (/terms)
 *
 * ⚠️  HARD BLOCKER: This page requires lawyer approval before publishing.
 *     All section copy marked [LEGAL REVIEW REQUIRED] must be replaced
 *     with lawyer-approved text before launch.
 *
 * CURRENT_TOS_VERSION = "1.0" — bump this in backend/app/models/user.py
 * when copy changes materially (triggers re-acceptance from all users).
 */
import type { Metadata } from 'next'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: 'Terms of Service — Clairo',
    description: 'Terms of Service for using Clairo.',
    robots: { index: false, follow: false },
  }
}

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-white px-5 py-10 max-w-2xl mx-auto">
      {/* DRAFT banner — remove ONLY after lawyer approval */}
      <div className="bg-warning-50 border border-warning-200 rounded-xl px-4 py-3 mb-8 text-sm text-warning-800">
        <strong>⚠️ DRAFT — Legal review required.</strong> This document has not been
        approved by legal counsel and must not be shown to users until approved.
        Version: 1.0 (draft)
      </div>

      <h1 className="text-2xl font-bold text-neutral-900 mb-2">Terms of Service</h1>
      <p className="text-sm text-neutral-500 mb-8">
        Last updated: <span className="font-medium">[DATE — LEGAL REVIEW REQUIRED]</span>
        {' · '}Version 1.0
      </p>

      <div className="prose prose-sm max-w-none text-neutral-700 space-y-6">
        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">1. What Clairo is</h2>
          <p>
            Clairo is a contract explanation tool. It uses artificial intelligence to
            explain what contracts say in plain language. It does not provide legal advice.
          </p>
          <p>
            <strong>Clairo is not a law firm.</strong> Clairo's explanations are for
            informational purposes only. Do not rely on Clairo's output as legal advice.
            Always consult a qualified lawyer before making legal decisions.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">2. Who can use Clairo</h2>
          <p>[LEGAL REVIEW REQUIRED — age requirements, geographic restrictions,
          prohibited uses (e.g. must not be used for unlawful purposes).]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">3. What we do with your documents</h2>
          <p>
            Your uploaded document is processed in memory only. It is:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Never stored on disk or in any database</li>
            <li>Never cached beyond the duration of a single analysis</li>
            <li>Deleted from memory immediately after analysis completes</li>
            <li>Sent to Anthropic for AI analysis under Anthropic's zero data retention policy</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">
            4. Prohibited document types
          </h2>
          <p>
            Clairo cannot analyse: court orders, immigration documents, medical consent
            forms, financial instruments (securities, derivatives), and documents
            involving minors. These require specialist professional advice.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">5. Limitation of liability</h2>
          <p>[LEGAL REVIEW REQUIRED — limitation clause, warranty disclaimer,
          exclusion of consequential loss. Must be jurisdiction-appropriate.]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">6. Intellectual property</h2>
          <p>[LEGAL REVIEW REQUIRED — who owns the analysis output; licence
          granted to user; user's IP in their uploaded documents.]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">7. Subscription and billing</h2>
          <p>[LEGAL REVIEW REQUIRED — subscription tiers, auto-renewal, refund
          policy, cancellation terms.]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">8. Account termination</h2>
          <p>[LEGAL REVIEW REQUIRED — grounds for termination, notice period,
          effect on subscription, data deletion on termination.]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">9. Governing law</h2>
          <p>[LEGAL REVIEW REQUIRED — governing law and jurisdiction. Must account
          for EU consumer law mandatory protections.]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">10. Changes to these terms</h2>
          <p>
            We will notify you of material changes by email and require you to accept
            updated terms before continuing to use Clairo. The version number above
            increments with each material change.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">11. Contact</h2>
          <p>[LEGAL REVIEW REQUIRED — contact details for legal notices.]</p>
        </section>
      </div>
    </main>
  )
}
