/**
 * CLR-039 — Privacy Policy page (/privacy)
 *
 * ⚠️  HARD BLOCKER: This page requires lawyer approval before publishing.
 *     All section copy marked [LEGAL REVIEW REQUIRED] must be replaced
 *     with lawyer-approved text before launch.
 *
 * Structure is complete. Replace placeholder sections with approved copy.
 * Do NOT remove the DRAFT banner until legal approval is confirmed.
 */
import type { Metadata } from 'next'
import { getTranslations } from 'next-intl/server'

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string }
}): Promise<Metadata> {
  return {
    title: 'Privacy Policy — Clairo',
    description: 'How Clairo handles your data and protects your privacy.',
    // Prevent indexing until legal approval
    robots: { index: false, follow: false },
  }
}

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-white px-5 py-10 max-w-2xl mx-auto">
      {/* DRAFT banner — remove ONLY after lawyer approval */}
      <div className="bg-warning-50 border border-warning-200 rounded-xl px-4 py-3 mb-8 text-sm text-warning-800">
        <strong>⚠️ DRAFT — Legal review required.</strong> This document has not been
        approved by legal counsel and must not be shown to users until approved.
      </div>

      <h1 className="text-2xl font-bold text-neutral-900 mb-2">Privacy Policy</h1>
      <p className="text-sm text-neutral-500 mb-8">
        Last updated: <span className="font-medium">[DATE — LEGAL REVIEW REQUIRED]</span>
      </p>

      <div className="prose prose-sm max-w-none text-neutral-700 space-y-6">
        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">1. Who we are</h2>
          <p>
            [LEGAL REVIEW REQUIRED — Insert registered company name, address, and data
            controller information. Include ICO registration number if UK-based.]
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">
            2. What data we collect
          </h2>
          <p>
            <strong>Account data:</strong> Email address, authentication provider (Google
            or magic link). Stored in our database via Clerk.
          </p>
          <p>
            <strong>Document data:</strong> Your uploaded document is processed in memory
            only. It is never stored on disk, in our database, or in any cache.
            It is deleted from memory immediately after analysis is complete.
          </p>
          <p>
            <strong>Usage data:</strong> [LEGAL REVIEW REQUIRED — specify analytics,
            usage logs, rate-limit counters retained and for how long.]
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">
            3. How we use your data
          </h2>
          <p>[LEGAL REVIEW REQUIRED — legal basis under GDPR Art. 6 for each
          processing activity. Likely: contract performance for analysis; legitimate
          interest for security logging; consent for analytics.]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">
            4. Third-party processors
          </h2>
          <p>
            We share data with the following sub-processors:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Anthropic</strong> — AI analysis. Zero data retention enabled on our account. Document content is deleted from Anthropic's systems immediately after processing.</li>
            <li><strong>Google Cloud Vision</strong> — OCR text extraction. [LEGAL REVIEW REQUIRED — confirm data retention policy and DPA status.]</li>
            <li><strong>AWS</strong> — Hosting, database, secrets management. [LEGAL REVIEW REQUIRED — confirm regions and DPA.]</li>
            <li><strong>Clerk</strong> — Authentication. [LEGAL REVIEW REQUIRED — data residency and DPA.]</li>
            <li><strong>Stripe</strong> — Payment processing. [LEGAL REVIEW REQUIRED — PCI DSS scope.]</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">
            5. International transfers
          </h2>
          <p>[LEGAL REVIEW REQUIRED — SCCs or adequacy decisions for each transfer
          to third countries. Particularly important for EU/UK users.]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">
            6. Your rights
          </h2>
          <p>
            You have the right to access, correct, and delete your personal data.
            To request deletion, [LEGAL REVIEW REQUIRED — specify process, e.g. email
            address or in-app delete button]. We will complete deletion within
            [LEGAL REVIEW REQUIRED — specify timeframe, e.g. 30 days].
          </p>
          <p>
            GDPR rights (EU/UK users): access, rectification, erasure, restriction,
            portability, objection. [LEGAL REVIEW REQUIRED — right to lodge complaint
            with supervisory authority.]
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">
            7. Data retention
          </h2>
          <p>
            <strong>Document content:</strong> Zero retention — deleted from memory
            immediately after analysis.
          </p>
          <p>
            <strong>Account data:</strong> Retained until you delete your account.
            Deletion is complete and immediate upon request (GDPR Art. 17).
          </p>
          <p>
            <strong>Audit logs:</strong> [LEGAL REVIEW REQUIRED — specify retention
            period for security audit logs.]
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">8. Cookies</h2>
          <p>[LEGAL REVIEW REQUIRED — specify cookies used, their purpose, and
          consent mechanism. ePrivacy Directive compliance required.]</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-neutral-900 mb-2">9. Contact</h2>
          <p>[LEGAL REVIEW REQUIRED — data controller contact details and DPO
          contact if required under GDPR Art. 37.]</p>
        </section>
      </div>
    </main>
  )
}
