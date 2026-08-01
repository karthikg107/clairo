# Clairo

**Understand any contract. In any language. Instantly.**

Clairo is an AI-powered contract analysis platform that explains legal
documents — leases, employment contracts, freelance agreements, terms of
service — in plain language, across 8 languages. Upload a PDF, DOCX, or a
photo of a document; Clairo extracts the text, classifies the document
type (and blocks prohibited categories like medical or immigration
documents), and returns a clause-by-clause explanation that flags what
protects you and what to review — never legal advice, never a verdict on
enforceability.

**Status: feature-complete and deployed.** Live on a free-tier stack:

- **App**: [clairo-sigma.vercel.app](https://clairo-sigma.vercel.app)
- **API**: [clairo-backend-zc0q.onrender.com](https://clairo-backend-zc0q.onrender.com)

## Features

- **Upload → OCR → classify → analyse** pipeline for PDF, DOCX, and photos
  (JPEG/PNG/HEIC — including iPhone photos)
- **Plain-language clause analysis** via an LLM (Anthropic Claude or
  OpenAI, pluggable) — flags protective clauses and clauses worth
  reviewing, cites frequency stats instead of legal opinions
- **Prohibited-document detection** — court orders, immigration, medical
  consent, and financial instruments are blocked before analysis, with a
  referral to an appropriate professional
- **8 languages**: English, Hindi, German, Spanish, Arabic, French,
  Portuguese, Urdu — including full RTL support
- **Free tier**: 2 lifetime analyses for anonymous visitors (tracked by
  IP + device id, no account needed), extendable via referrals
- **Shareable analysis links** (`/s/[id]`) — a sanitised, read-only view
  with no document content, auto-expiring, revocable, rate-limited
- **Referral programme** — both sides get a bonus analysis
- **Accounts & billing** via Clerk (auth) and Stripe (subscriptions)
- **PWA** — installable, with offline access to your 10 most recent
  analyses
- **Localised landing + country pages** (`/de`, `/uk`, `/in`, `/ae`) with
  IP-geolocation redirect and hreflang tags
- **GDPR tooling** — data export, account deletion (hard delete within
  30s), consent-gated analytics (PostHog)
- **Security hardening** — rate limiting, an input firewall (SQLi/XSS
  pattern detection on request paths), Origin verification on
  state-changing requests, structured security-event logging with Sentry
  alerts, strict CSP/HSTS/security headers, append-only audit log

## Tech Stack

**Frontend**

- Next.js 14 (App Router) + TypeScript + Tailwind CSS
- next-intl for i18n and locale routing
- Clerk for authentication
- Deployed on Vercel

**Backend**

- FastAPI (Python 3.12), fully async (SQLAlchemy + asyncpg)
- PostgreSQL — schema versioned with Alembic
- Redis — rate limiting, quota tracking, analysis caching
- LLM analysis: Anthropic Claude (default) or OpenAI, switchable via
  `LLM_PROVIDER` with no code change
- OCR: free in-container Tesseract (default) or Google Cloud Vision +
  AWS Textract fallback, switchable via `OCR_PROVIDER`
- Stripe for billing, PostHog for consent-gated analytics, Sentry for
  error/security monitoring
- Deployed on Render (Docker), with a self-healing Alembic migration on
  every boot
- Secrets: AWS Secrets Manager in production, or plain environment
  variables via `SECRETS_BACKEND=env` for non-AWS hosts

## Prerequisites

- Node.js ≥ 20 and npm
- Python ≥ 3.12
- A local or hosted PostgreSQL instance and Redis instance (optional in
  dev — most endpoints fail open without Redis; Postgres is required for
  any authenticated/account feature)

## Local Setup

### Frontend

```bash
git clone https://github.com/karthikg107/clairo.git
cd clairo

npm install
cp .env.local.example .env.local
# Fill in .env.local — at minimum NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
# CLERK_SECRET_KEY, and NEXT_PUBLIC_API_URL (your backend's URL)

npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate   # Windows; use .venv/bin/activate on macOS/Linux

pip install -r requirements-dev.txt
cp .env.example .env
# Fill in .env — ANTHROPIC_API_KEY (or OPENAI_API_KEY + LLM_PROVIDER=openai),
# DATABASE_URL, CLERK_SECRET_KEY, CLERK_ISSUER

alembic upgrade head
python run_dev.py
```

The API runs on [http://localhost:8000](http://localhost:8000).

## Available Scripts

**Frontend** (repo root)

| Command              | Description                  |
| -------------------- | ---------------------------- |
| `npm run dev`        | Start dev server on :3000    |
| `npm run build`      | Production build             |
| `npm run start`      | Start production server      |
| `npm run lint`       | Run ESLint                   |
| `npm run type-check` | Run `tsc --noEmit`           |
| `npm run test:e2e`   | Run the Playwright E2E suite |

**Backend** (`backend/`)

| Command                | Description                                 |
| ---------------------- | ------------------------------------------- |
| `python run_dev.py`    | Start the dev server on :8000 (auto-reload) |
| `pytest`               | Run the test suite (472 tests)              |
| `ruff check .`         | Lint                                        |
| `alembic upgrade head` | Apply database migrations                   |

## Project Structure

```
clairo/
├── app/                    # Next.js App Router
│   ├── [locale]/           # Locale-prefixed routes (upload, dashboard,
│   │                       #   pricing, account, s/[shareId], ref/[userId]…)
│   └── globals.css
├── components/              # ui/, forms/, results/, upload/, landing/…
├── lib/                    # i18n config, analytics, pricing, utils
├── locales/                # Translation JSON — en, hi, de, es, ar, fr, pt, ur
├── e2e/                    # Playwright end-to-end tests
├── docs/                   # GDPR register, security config, launch
│                           #   checklist, runbooks, pen-test brief
├── monitoring/             # Uptime checks, AWS budget alert config
├── middleware.ts           # Locale routing + Clerk route protection
│
└── backend/
    ├── app/
    │   ├── api/v1/endpoints/   # upload, ocr, classify, analyse, share,
    │   │                       #   billing, account, referrals, health…
    │   ├── core/               # config, rate limiting, security events,
    │   │                       #   secrets resolution
    │   ├── middleware/         # JWT auth, rate limiting, security guard
    │   ├── models/              # SQLAlchemy models
    │   └── services/            # ocr, document_type, analysis, quota…
    ├── alembic/                 # Database migrations
    └── tests/                   # 472 tests
```

## Supported Languages

| Code | Language   | RTL |
| ---- | ---------- | --- |
| en   | English    | No  |
| hi   | Hindi      | No  |
| de   | German     | No  |
| es   | Spanish    | No  |
| ar   | Arabic     | Yes |
| fr   | French     | No  |
| pt   | Portuguese | No  |
| ur   | Urdu       | Yes |

## Security Notes

- Document content is **never stored** — processed in memory only, purged
  immediately after OCR; no document/OCR-text columns exist anywhere in
  the schema
- Every database query is parameterised (SQLAlchemy ORM or bound raw SQL)
- Request-level input firewall detects SQLi/XSS/path-traversal patterns
  on the request path and query string (never the body, which may
  legitimately contain document text)
- Origin verification on all state-changing requests (the appropriate
  CSRF control for a Bearer-token API)
- Full security headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- Append-only audit log (the app's database role has INSERT-only access —
  enforced at the database level, not just in application code)
- Secrets are never hardcoded — resolved from AWS Secrets Manager in
  production, or explicit environment variables via `SECRETS_BACKEND=env`
- See [`docs/clerk-security-config.md`](docs/clerk-security-config.md) for
  the auth-layer controls (login rate limiting, lockout, session limits)
  that are configured in Clerk rather than in this codebase

## Testing

- **Backend**: 472 tests (`cd backend && pytest`) — unit and integration
  coverage for every service, endpoint, and security control
- **E2E**: Playwright coverage (`npm run test:e2e`) for the core user
  journeys — upload → analysis, free-tier limits, shared links,
  prohibited-document blocking, and the sign-up → analysis flow

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Private — all rights reserved.
