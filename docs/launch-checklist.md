# CLR-057 — Pre-Launch Checklist & Go-Live Procedure

> **HUMAN-DRIVEN.** This is the go/no-go gate for production launch. Each
> item has an **owner role** and a **state**. Launch only when every P0
> item is ✅. Code-side readiness is largely done (Epics 1–10); the open
> items are infrastructure, legal, and the two testing tickets
> (CLR-052, CLR-053) that require humans.
>
> States: ☐ not started · ◐ in progress · ✅ done · N/A

Owner roles: **ENG** (engineering), **LEGAL** (counsel), **OPS**
(infra/on-call), **PM** (product), **DESIGN**.

---

## 1. Legal & compliance (blocks launch)

| P   | Item                                                                                                                                               | Owner     | State |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ----- |
| P0  | Privacy Policy replaced with lawyer-approved copy; remove DRAFT banner and all `[LEGAL REVIEW REQUIRED]` markers (`app/[locale]/privacy/page.tsx`) | LEGAL     | ☐     |
| P0  | Terms of Service approved; `[LEGAL REVIEW REQUIRED]` markers resolved (`app/[locale]/terms/page.tsx`)                                              | LEGAL     | ☐     |
| P0  | GDPR processing register completed & signed off (`docs/gdpr-processing-register.md`) — controller entity, DPO, transfer mechanisms/SCCs            | LEGAL     | ☐     |
| P0  | Data export scope legally confirmed to satisfy Art. 15/20                                                                                          | LEGAL     | ☐     |
| P0  | Sub-processor DPAs in place (Anthropic, Google, AWS, Clerk, Stripe, PostHog)                                                                       | LEGAL     | ☐     |
| P0  | Anthropic zero-data-retention confirmed in writing on the production account                                                                       | LEGAL/ENG | ☐     |
| P1  | Cookie/consent copy reviewed; lead supervisory authority named                                                                                     | LEGAL     | ☐     |
| P1  | Prohibited-document referral organisations (per country) legally reviewed                                                                          | LEGAL     | ☐     |

## 2. Security (blocks launch)

| P   | Item                                                                                                                                   | Owner | State |
| --- | -------------------------------------------------------------------------------------------------------------------------------------- | ----- | ----- |
| P0  | Independent penetration test completed (CLR-053, `docs/pentest-brief.md`)                                                              | OPS   | ☐     |
| P0  | All critical/high pentest findings remediated + retested                                                                               | ENG   | ☐     |
| P0  | Production secrets in AWS Secrets Manager, not env files; rotated from any dev values (`clairo/anthropic`, `clairo/stripe`, DB, Clerk) | OPS   | ☐     |
| P0  | `X-Clerk-User-Id` dev-fallback header disabled/ignored in production                                                                   | ENG   | ☐     |
| P0  | `NEXT_PUBLIC_E2E_MODE` confirmed unset in all deployed environments (would bypass Clerk)                                               | OPS   | ☐     |
| P0  | HTTPS/HSTS enforced; security headers (CSP, X-Frame-Options) verified live                                                             | OPS   | ☐     |
| P1  | ClamAV virus scanning live and reachable from the API                                                                                  | OPS   | ☐     |
| P1  | Rate limits validated against production Redis                                                                                         | ENG   | ☐     |

## 3. Infrastructure & data

| P   | Item                                                                                              | Owner | State |
| --- | ------------------------------------------------------------------------------------------------- | ----- | ----- |
| P0  | Production Postgres provisioned; **all Alembic migrations applied** (head `20240709_0001`)        | OPS   | ☐     |
| P0  | Production Redis provisioned (rate limits, quota, cache, circuit breaker)                         | OPS   | ☐     |
| P0  | `gdpr_delete_user()` verified against production schema (deletion < 30s)                          | ENG   | ☐     |
| P0  | Automated DB backups enabled + a restore test performed                                           | OPS   | ☐     |
| P0  | Custom domains + TLS: `clairo.app` (web) and `api.clairo.app` (API)                               | OPS   | ☐     |
| P1  | Frontend `NEXT_PUBLIC_API_URL` points at the production API origin; CSP `connect-src` includes it | ENG   | ☐     |
| P1  | Stripe webhook endpoint registered at the production URL with the production signing secret       | OPS   | ☐     |
| P1  | Stripe products/prices created; price IDs in `clairo/stripe` secret                               | OPS   | ☐     |
| P1  | Clerk production instance; JWKS/issuer configured; keys in env                                    | OPS   | ☐     |

## 4. Monitoring & on-call (CLR-056)

| P   | Item                                                                                         | Owner | State |
| --- | -------------------------------------------------------------------------------------------- | ----- | ----- |
| P0  | Sentry project created; `SENTRY_DSN` set in backend prod secrets                             | OPS   | ☐     |
| P0  | Sentry → Slack `#clairo-alerts` integration; email backup configured                         | OPS   | ☐     |
| P0  | Sentry alert rules created (`monitoring/README.md`): error rate >1%/5min, operational alerts | OPS   | ☐     |
| P0  | Uptime checks live (`monitoring/uptime-checks.yml`) — landing, api-health, api-ready         | OPS   | ☐     |
| P1  | AWS Budgets cost alert at 120% of daily budget (`monitoring/aws-budget*.json`)               | OPS   | ☐     |
| P1  | Anthropic console spend limit set                                                            | OPS   | ☐     |
| P0  | On-call rotation defined; runbooks reviewed by on-call (`docs/runbooks.md`)                  | OPS   | ☐     |

## 5. Quality & testing

| P   | Item                                                                                      | Owner      | State                    |
| --- | ----------------------------------------------------------------------------------------- | ---------- | ------------------------ |
| P0  | Playwright E2E suite green against staging (CLR-054)                                      | ENG        | ✅ (local) → ☐ (staging) |
| P0  | Signed-in E2E variant run with real Clerk test keys (`E2E_CLERK_KEYS`)                    | ENG        | ☐                        |
| P0  | Backend test suite green (440 tests)                                                      | ENG        | ✅                       |
| P0  | Cross-browser/device testing signed off (CLR-052, `docs/device-testing-matrix.md`)        | DESIGN/ENG | ☐                        |
| P0  | Accessibility: WCAG 2.1 AA verified (CLR-051) incl. manual screen-reader pass on staging  | DESIGN     | ◐ (axe ✅, manual ☐)     |
| P0  | Lighthouse mobile performance >90 confirmed on the deployed landing (CLR-050)             | ENG        | ☐ (needs prod deploy)    |
| P1  | Full analysis journey smoke-tested on staging with a real Claude key + synthetic document | ENG        | ☐                        |

## 6. Product & content

| P   | Item                                                                               | Owner    | State |
| --- | ---------------------------------------------------------------------------------- | -------- | ----- |
| P1  | All 8 locales proofread by native speakers (esp. legal-adjacent copy)              | PM       | ☐     |
| P1  | Country landing pages (DE/UK/IN/AE) reviewed for local accuracy (CLR-049)          | PM/LEGAL | ☐     |
| P1  | OG/preview images render correctly when a share link is posted to WhatsApp/Twitter | DESIGN   | ☐     |
| P2  | Pricing confirmed correct across currencies; annual discount math checked          | PM       | ☐     |
| P2  | Support/contact channel live (referenced in Privacy Policy §9)                     | OPS      | ☐     |

## 7. Go-live procedure (execution day)

1. **Freeze** — no non-launch merges to `main`.
2. Final `main` build passes CI (lint, typecheck, backend tests, E2E).
3. Apply DB migrations to production; verify head revision.
4. Deploy API; confirm `/api/v1/health` and `/api/v1/ready` are 200.
5. Deploy web; confirm landing renders and a country redirect works.
6. Smoke test on production: landing → upload a SYNTHETIC document →
   analysis → share; sign-up → dashboard; one paid checkout with a live
   card in test mode if possible, else immediately post-launch.
7. Confirm Sentry receives a test event and Slack alert fires.
8. Remove the Privacy/Terms DRAFT banners (only after LEGAL sign-off).
9. Enable production analytics key (consent-gated already).
10. Announce. Watch `#clairo-alerts` and Sentry for the first 24h.

## 8. Rollback triggers & procedure

Roll back immediately if any of:

- Error rate >5% sustained 10 min, or circuit breaker cycling >10 min.
- Any confirmed document-content leak (**hard stop — pull the release**).
- Auth broken (users seeing others' data) — **hard stop**.
- Payment capture failing.

Procedure: redeploy the previous release tag; migrations in this launch
are additive (no destructive down-migrations needed); post a status
update; open a P1 incident and follow `docs/runbooks.md`.

---

### Launch decision

Go/no-go sign-off required from: **ENG lead**, **OPS/on-call**,
**LEGAL**, **PM**. Record names, date, and any accepted-risk exceptions
here before flipping production live.
