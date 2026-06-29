# Clairo

**Understand any contract. In any language. Instantly.**

Clairo is an AI-powered contract analysis platform that helps non-lawyers understand legal documents in plain language across 8 languages.

## Tech Stack

- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind CSS
- **i18n**: next-intl (8 languages: EN, HI, DE, ES, AR, FR, PT, UR)
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL (AWS RDS)
- **Cache**: Redis (AWS ElastiCache)
- **AI**: Anthropic Claude (via API)
- **OCR**: Google Cloud Vision
- **Auth**: Clerk
- **Payments**: Stripe
- **Infra**: Vercel (frontend) + AWS ECS (backend)

## Prerequisites

- Node.js ≥ 20
- pnpm ≥ 9
- Python ≥ 3.12 (for backend)

## Setup

```bash
# 1. Clone
git clone https://github.com/karthikguttula107/clairo.git
cd clairo

# 2. Install dependencies
pnpm install

# 3. Set up environment
cp .env.local.example .env.local
# Fill in .env.local with your values (see env var docs)

# 4. Run dev server
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).

## Available Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start dev server on :3000 |
| `pnpm build` | Production build |
| `pnpm start` | Start production server |
| `pnpm lint` | Run ESLint |
| `pnpm type-check` | Run `tsc --noEmit` |

## Project Structure

```
clairo/
├── app/
│   ├── [locale]/          # Locale-prefixed routes
│   │   ├── layout.tsx     # Locale layout (fonts, RTL, i18n)
│   │   └── page.tsx       # Home page
│   ├── globals.css
│   └── layout.tsx         # Root layout
├── components/
│   ├── ui/                # Primitive components (Button, Card, Badge…)
│   ├── layouts/           # Page-level layouts (AppShell, AuthLayout…)
│   └── forms/             # Form components (UploadForm, FileInput…)
├── lib/
│   ├── i18n/              # next-intl request config
│   └── utils/             # cn(), formatters, etc.
├── locales/               # Translation JSON (en, hi, de, es, ar, fr, pt, ur)
├── types/                 # Shared TypeScript types
├── public/
└── middleware.ts          # next-intl routing middleware
```

## Supported Languages

| Code | Language | RTL |
|------|----------|-----|
| en | English | No |
| hi | Hindi | No |
| de | German | No |
| es | Spanish | No |
| ar | Arabic | Yes |
| fr | French | No |
| pt | Portuguese | No |
| ur | Urdu | Yes |

## Security Notes

- Document content is **never stored** — processed in memory only, purged immediately after OCR
- No document content columns exist in the database schema
- All secrets fetched from AWS Secrets Manager at runtime (never environment variables in production)
- Zero data retention enabled on Anthropic API account
- Audit log is write-only (no UPDATE/DELETE for app user)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Private — all rights reserved.
