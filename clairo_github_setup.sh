#!/usr/bin/env bash
# clairo_github_setup.sh
# Creates the clairo GitHub repo, labels, milestones, and all 57 issues.

set -euo pipefail

REPO="clairo"
OWNER=$(gh api user --jq .login)
FULL_REPO="$OWNER/$REPO"

echo "==> Creating private repo: $FULL_REPO"
gh repo create clairo --private --description "Understand any contract. In any language. Instantly." || echo "Repo may already exist, continuing..."

echo ""
echo "==> Creating labels"

lbl() {
  gh label create "$1" --color "$2" --description "$3" --repo "$FULL_REPO" --force
}

# Priority
lbl "P0-critical"          "B91C1C" "Must ship for MVP"
lbl "P1-high"              "E85D2F" "Ship within 60 days"
lbl "P2-roadmap"           "1B4F8A" "Future roadmap"

# Size
lbl "size-S"               "1A7A4A" "Half day"
lbl "size-M"               "2E6DB4" "1 day"
lbl "size-L"               "B36200" "2-3 days"

# Type
lbl "type-feature"         "0EA5E9" ""
lbl "type-infrastructure"  "8B5CF6" ""
lbl "type-security"        "EF4444" ""
lbl "type-legal"           "F97316" ""

# Sprints
for i in 1 2 3 4 5 6; do
  lbl "sprint-$i" "0EA5E9" "Sprint $i"
done

# Epics
lbl "epic-1-setup"         "1B4F8A" "Epic 1: Setup & Infrastructure"
lbl "epic-2-upload"        "1B4F8A" "Epic 2: Upload Flow"
lbl "epic-3-ai"            "1B4F8A" "Epic 3: AI Analysis"
lbl "epic-4-results"       "1B4F8A" "Epic 4: Auth & Accounts"
lbl "epic-5-payments"      "1B4F8A" "Epic 5: Payments"
lbl "epic-6-accounts"      "1B4F8A" "Epic 6: Security"
lbl "epic-7-growth"        "1B4F8A" "Epic 7: Legal"
lbl "epic-8-quality"       "1B4F8A" "Epic 8: Sharing & Viral"
lbl "epic-9-security"      "1B4F8A" "Epic 9: PWA & Landing"
lbl "epic-10-launch"       "1B4F8A" "Epic 10: Quality & Launch"

echo ""
echo "==> Creating milestones"

ms() {
  gh api "repos/$FULL_REPO/milestones" \
    -f title="$1" -f due_on="${2}T23:59:59Z" -f description="$3" --silent || true
}

ms "Sprint 1 Foundation"          "2026-07-11" "Core infrastructure and project setup"
ms "Sprint 2 Upload+AI"           "2026-07-25" "Document upload and AI analysis pipeline"
ms "Sprint 3 Results+Payments"    "2026-08-08" "Results UI and payment integration"
ms "Sprint 4 Accounts+Growth"     "2026-08-22" "User accounts and growth features"
ms "Sprint 5 Quality+Security"    "2026-09-05" "Quality assurance and security hardening"
ms "Sprint 6 Launch"              "2026-09-19" "Final polish and public launch"

echo ""
echo "==> Creating 57 issues"

# Helper: write body to temp file, create issue, clean up
gi() {
  local title="$1" labels="$2" milestone="$3"
  gh issue create \
    --repo "$FULL_REPO" \
    --title "$title" \
    --body-file /tmp/_clairo_body.md \
    --label "$labels" \
    --milestone "$milestone"
  echo "  created: $title"
  rm -f /tmp/_clairo_body.md
}


# CLR-001
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Create base Next.js 14 project with TypeScript, Tailwind CSS, and correct folder structure for a scalable PWA. Set up linting, formatting, and git hooks.

## Acceptance Criteria
- Next.js 14 with App Router and TypeScript strict mode
- Tailwind configured with Clairo tokens: brand #1B4F8A, accent #E85D2F, success #1A7A4A, warning #B36200, danger #B91C1C
- Folders: /app /components /lib /hooks /styles /locales /types
- ESLint + Prettier + Husky pre-commit hooks
- .env.local template committed, real values never committed
- Deployed to Vercel preview URL
- README with setup instructions
BODY_END
gi 'CLR-001 | Init Next.js 14 project with Tailwind, TypeScript and folder structure' 'epic-1-setup,sprint-1,P0-critical,size-M,type-infrastructure' 'Sprint 1 Foundation'

# CLR-002
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Initialise Python FastAPI backend for all document processing, AI calls, and API logic.

## Acceptance Criteria
- FastAPI with Python 3.11+
- Folders: /routers /services /models /utils
- GET /health returns 200 with status and version
- CORS: only clairo.app and localhost:3000
- Deployed to AWS Lambda
- Structured JSON logging — no document content ever logged
- requirements.txt with pinned versions
BODY_END
gi 'CLR-002 | Set up FastAPI backend with project structure and health check' 'epic-1-setup,sprint-1,P0-critical,size-M,type-infrastructure' 'Sprint 1 Foundation'

# CLR-003
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
PostgreSQL database with correct schema. No document content fields anywhere.

## Acceptance Criteria
- PostgreSQL on AWS RDS with encryption at rest
- Table users: id, email_hash, created_at, subscription_tier, analysis_count
- Table audit_log: id, user_id, timestamp, document_type, doc_language, output_language, page_count, processing_ms, success
- NO document content columns exist anywhere in schema
- Alembic migrations set up
- Credentials in AWS Secrets Manager
- Read-only replica for analytics
- audit_log is write-only — no UPDATE or DELETE for app user
BODY_END
gi 'CLR-003 | Set up PostgreSQL database with schema and migrations' 'epic-1-setup,sprint-1,P0-critical,size-M,type-infrastructure' 'Sprint 1 Foundation'

# CLR-004
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Redis for session tokens, rate limit counters, and clause template cache.

## Acceptance Criteria
- Redis on AWS ElastiCache with encryption at rest
- Key naming: rate_limit:{ip}, session:{token}, cache:{doc_hash}
- TTLs: rate limit 1hr, session 1hr, cache 30 days
- Redis never stores document content
BODY_END
gi 'CLR-004 | Set up Redis for session cache and rate limiting' 'epic-1-setup,sprint-1,P0-critical,size-S,type-infrastructure' 'Sprint 1 Foundation'

# CLR-005
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
i18n from day one. All UI strings in translation files — no hardcoded text anywhere.

## Acceptance Criteria
- next-i18next installed and configured
- Locale files for: en, hi, de, es, ar, fr, pt, ur
- RTL support for ar and ur (dir=rtl applied automatically)
- Browser language as default, overridden by user preference
- All strings in locale files — zero hardcoded UI text
- Date and number formatting locale-aware
- Language switcher component built
BODY_END
gi 'CLR-005 | Set up next-i18next with 8 launch languages' 'epic-1-setup,sprint-1,P0-critical,size-M,type-infrastructure' 'Sprint 1 Foundation'

# CLR-006
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Automated testing and deployment so every change is tested before going live.

## Acceptance Criteria
- GitHub Actions: lint, type check, unit tests, build
- All checks pass before merge to main
- Auto preview deployment to Vercel on every PR
- Auto production deployment on merge to main
- Secret scanning — committed secrets block the push
- Dependabot for dependency vulnerability scanning
BODY_END
gi 'CLR-006 | Set up CI/CD pipeline with automated tests and deployment' 'epic-1-setup,sprint-1,P0-critical,size-M,type-infrastructure' 'Sprint 1 Foundation'

# CLR-007
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
File upload UI (SCR-04). PDF, DOCX, images. Client-side validation with clear errors.

## Acceptance Criteria
- Drag-and-drop zone highlights on drag-over (brand-500 border, brand-100 background)
- Tap to select works on mobile
- Accepted: PDF, DOCX, JPG, PNG, HEIC — others rejected with clear message
- Files over 25MB rejected immediately
- File name and size shown after selection
- Three options: Upload file, Take photo, Upload photo from gallery
- Privacy reminder visible without scrolling on 375px screen
- All strings in i18n files
- Accessible: keyboard navigable, screen reader support
- HEIC must work (iPhone users photographing contracts)
BODY_END
gi 'CLR-007 | Build file upload component with drag-and-drop and validation' 'epic-2-upload,sprint-1,P0-critical,size-M,type-feature' 'Sprint 1 Foundation'

# CLR-008
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Custom camera interface (SCR-05) with real-time quality detection. Not the system camera.

## Acceptance Criteria
- Custom camera view using MediaDevices.getUserMedia — NOT input[type=file]
- Real-time document edge detection with animated corner guides (green when detected)
- Live quality score 0-100% displayed
- Instruction text updates: lighting, angle, distance, motion issues
- Auto-capture at 80%+ quality with 3-2-1 countdown
- Manual capture button always available
- Torch/flash toggle for supported devices
- Quality under 50% after manual capture: warning + retake option
- Portrait and landscape supported
- Camera permission denied: graceful fallback to photo upload
- Captured image compressed to max 4000x4000px before upload
BODY_END
gi 'CLR-008 | Build guided camera capture with real-time quality scoring' 'epic-2-upload,sprint-2,P0-critical,size-L,type-feature' 'Sprint 2 Upload+AI'

# CLR-009
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Server-side validation before any processing. MIME + magic bytes + virus scan.

## Acceptance Criteria
- POST /api/upload/validate endpoint
- MIME type checked against allowlist (pdf, docx, jpeg, png, heic)
- Magic bytes from first 8 bytes must match declared MIME type
- ClamAV scan — file rejected if any signature matches
- Files over 25MB rejected with 413
- File never written to disk — processed in memory only
- All failures logged (event type only, no file content)
- ClamAV definitions updated daily via cron
BODY_END
gi 'CLR-009 | Build backend file validation with MIME checking and ClamAV virus scan' 'epic-2-upload,sprint-1,P0-critical,size-M,type-security' 'Sprint 1 Foundation'

# CLR-010
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
OCR service using Google Cloud Vision with per-word confidence scores. Textract fallback.

## Acceptance Criteria
- POST /api/ocr endpoint
- Google Cloud Vision with DOCUMENT_TEXT_DETECTION
- Per-word confidence scores returned (0-100)
- Words categorised: high >80%, medium 50-80%, low <50%
- ALL numbers flagged as always-verify regardless of confidence
- Auto-retry with AWS Textract if Google Vision fails
- PDF/DOCX: text extracted directly, confidence assumed 100%
- Document purged from memory immediately after OCR
- Test with Arabic, Hindi, German documents before marking done
BODY_END
gi 'CLR-010 | Build OCR pipeline with Google Vision API and confidence scoring' 'epic-2-upload,sprint-2,P0-critical,size-L,type-infrastructure' 'Sprint 2 Upload+AI'

# CLR-011
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Mandatory verification screen (SCR-06) after OCR for image/camera uploads. Cannot be skipped.

## Acceptance Criteria
- Full extracted text shown in JetBrains Mono font
- Yellow highlight: 50-80% confidence words
- Red highlight + underline: below 50% confidence
- Orange highlight: ALL numbers regardless of confidence
- Tap any highlighted word: inline edit field with current text pre-filled
- After correction: highlight turns neutral with checkmark
- Warning box always visible: check all dates, amounts, time periods
- If more than 10% words red: prominent warning recommending retake
- Primary CTA: This looks correct — analyse (disabled if uncorrected red words)
- Secondary: Retake photo / Upload different file
- Screen SKIPPED for PDF/DOCX inputs
- Long documents paginated — do not render 50 pages in one scroll
- This screen is non-negotiable — cannot be skipped or A/B tested away
BODY_END
gi 'CLR-011 | Build pre-analysis text review screen with inline corrections' 'epic-2-upload,sprint-2,P0-critical,size-L,type-feature' 'Sprint 2 Upload+AI'

# CLR-012
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Detect document language after OCR and warn if it differs from user selection.

## Acceptance Criteria
- Language detection runs on extracted text
- If detected differs from user-selected: warning shown with option to change
- User can override and continue
- Detection result in audit log
- Supports all 20+ document languages
BODY_END
gi 'CLR-012 | Build document language detection and mismatch warning' 'epic-2-upload,sprint-2,P0-critical,size-M,type-feature' 'Sprint 2 Upload+AI'

# CLR-013
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Detect document type. Block prohibited types with clear message and professional referral.

## Acceptance Criteria
- Claude classifies type from first 500 words
- Types: rental, employment, freelance, tos, other_permitted, prohibited
- Prohibited: court_order, immigration, medical_consent, financial_instrument, minor_involved
- If prohibited: processing stops, clear message + referral shown
- Free analysis count NOT decremented for prohibited docs
- Type passed to analysis prompt
- Test with real examples of each prohibited type before marking done
BODY_END
gi 'CLR-013 | Build document type detection and prohibited type blocking' 'epic-2-upload,sprint-2,P0-critical,size-M,type-security' 'Sprint 2 Upload+AI'

# CLR-014
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
User selects document language, country (legal context), and explanation language.

## Acceptance Criteria
- Three searchable dropdowns: document language, country, explanation language
- Document language: 20+ languages with flag icons
- Country: 40+ countries with tooltip explaining it sets legal context
- Explanation language: each shown in English AND native script (e.g. Hindi — हिन्दी)
- CTA disabled until all 3 fields completed
- Confidence indicator appears after language pair selected
- High confidence: green badge. Medium: amber badge with explanation.
- Returning user: last-used preferences pre-filled
BODY_END
gi 'CLR-014 | Build language selection screen (SCR-03)' 'epic-2-upload,sprint-1,P0-critical,size-M,type-feature' 'Sprint 1 Foundation'

# CLR-015
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Core Claude API service. Structured JSON output required. Never log document content.

## Acceptance Criteria
- POST /api/analyse accepts: verified_text, doc_language, country, output_language, document_type
- Model: claude-sonnet-4-6
- System prompt hardcoded — cannot be overridden by any input
- Document content passed as user message data, never as system message
- Claude returns strict JSON schema (see CLAIRO_CONTEXT.md for schema)
- JSON validated against schema — deviation returns error not partial result
- Zero data retention enabled on Anthropic API account
- API key from AWS Secrets Manager only — never from environment variable
BODY_END
gi 'CLR-015 | Build Claude API integration with structured JSON output' 'epic-3-ai,sprint-2,P0-critical,size-L,type-infrastructure' 'Sprint 2 Upload+AI'

# CLR-016
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Claude system prompt enforcing all legal safety rules. Requires legal advisor approval.

## Acceptance Criteria
- Prompt rules: explain not advise, no jurisdiction-specific claims, no enforceability statements
- Describes clause frequency as statistics: Found in X% of similar contracts
- Flags clauses that PROTECT the user (not just unusual ones)
- Outputs in specified explanation language
- Applies specified country legal context for norms
- Tested with 20 diverse real contracts across 5 document types
- Legal advisor reviewed and approved in writing
- 20 prompt injection attempts all fail
- HARD BLOCKER: legal advisor approval required
BODY_END
gi 'CLR-016 | Build explain-not-advise system prompt with legal safety guardrails' 'epic-3-ai,sprint-2,P0-critical,size-M,type-legal' 'Sprint 2 Upload+AI'

# CLR-017
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Real-time progress screen during analysis. Never shows blank screen or just spinner.

## Acceptance Criteria
- Shows document language + explanation language pair
- Four sequential steps: Reading document, Identifying clauses, Generating explanation, Almost ready
- Each step appears when backend signals via WebSocket or polling
- Indeterminate but smooth progress bar
- Estimated time: Usually 20-40 seconds
- Privacy reminder: Processed securely. Deleted when done.
- Cancel button with confirmation dialog
- If exceeds 45 seconds: extra encouragement message
- Timeout at 90 seconds: error screen, document confirmed deleted
- Never shows blank screen or just a spinner
BODY_END
gi 'CLR-017 | Build processing status screen (SCR-07)' 'epic-3-ai,sprint-2,P0-critical,size-M,type-feature' 'Sprint 2 Upload+AI'

# CLR-018
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Core product screen. Summary, expandable clause cards, flags, frequencies, source text toggle.

## Acceptance Criteria
- Sticky header: document type, language pair, share button
- Legal disclaimer banner permanently visible — cannot be dismissed, ever
- Summary card at top with document overview
- Clause cards in document order, expandable on tap
- Each card: title in output language, flag badge, frequency stat, explanation in Source Serif 4 font
- Show original text toggle: source text in JetBrains Mono
- Numbers in explanation are tappable — tap highlights matching number in source text
- Flag badges: green Protects you (success-700), amber Less common (warning-700)
- Find a professional card at bottom — country-specific referral link
- Share button: WhatsApp primary, copy link, native share
- RTL: entire card flips for Arabic/Urdu output language
- Upgrade prompt only shown AFTER user scrolls past 2+ clauses
- Legal disclaimer is non-negotiable and non-dismissable
BODY_END
gi 'CLR-018 | Build analysis results screen with clause cards (SCR-08)' 'epic-3-ai,sprint-3,P0-critical,size-L,type-feature' 'Sprint 3 Results+Payments'

# CLR-019
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Cache analysis results in Redis to reduce API cost and improve speed.

## Acceptance Criteria
- SHA-256 hash of verified text computed
- Check Redis before calling Claude
- Cache hit: return immediately
- Cache miss: analyse, store with 30-day TTL
- Cache key: analysis:{sha256}:{output_language}:{country}
- Cache stores only analysis JSON — never document content
- Manual flush capability for legal review updates
BODY_END
gi 'CLR-019 | Build analysis caching for common contract templates' 'epic-3-ai,sprint-3,P0-critical,size-M,type-infrastructure' 'Sprint 3 Results+Payments'

# CLR-020
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Graceful failure modes. Document always confirmed deleted. User never sees unhandled error.

## Acceptance Criteria
- Timeout 30s: retry once then error
- Unavailable: clear error, document confirmed deleted
- Malformed JSON: one correction retry then error
- All error paths confirm document not stored
- Sentry alert on error rate above 1%
- Circuit breaker: 5 failures in 1 minute pauses analyses for 60 seconds
BODY_END
gi 'CLR-020 | Build fallback and error handling for Claude API failures' 'epic-3-ai,sprint-3,P0-critical,size-M,type-infrastructure' 'Sprint 3 Results+Payments'

# CLR-021
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Clerk for auth. Magic link primary. No passwords anywhere.

## Acceptance Criteria
- Clerk in Next.js project
- Magic link email flow working end-to-end
- Google OAuth as secondary option
- JWT with 1-hour expiry, refresh token rotation
- Protected routes return 401 for unauthenticated
- User record in PostgreSQL on first login with email hash (not plain email)
- New device login: email notification sent
BODY_END
gi 'CLR-021 | Set up Clerk authentication with magic link and Google OAuth' 'epic-4-results,sprint-2,P0-critical,size-M,type-infrastructure' 'Sprint 2 Upload+AI'

# CLR-022
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Mandatory screen before first upload. Cannot be skipped. Legal protection mechanism.

## Acceptance Criteria
- Full-screen overlay before first upload — not a modal
- Three trust statements with large checkmark icons (success-700)
- Statement 1: Your document is deleted immediately after analysis. It is never saved.
- Statement 2: Your document is never shared with anyone or used for AI training.
- Statement 3: This is not legal advice. We explain. You decide.
- Single CTA: I understand — continue. No skip. No X. No dismiss.
- Links to TOS and Privacy Policy functional
- Acceptance stored in localStorage AND user account
- Screen not shown again after acceptance
- Translated into all 8 languages
- Legal advisor approved exact wording
- HARD BLOCKER: requires TOS/Privacy Policy pages to exist first
BODY_END
gi 'CLR-022 | Build trust screen and TOS acceptance flow (SCR-02)' 'epic-4-results,sprint-2,P0-critical,size-M,type-legal' 'Sprint 2 Upload+AI'

# CLR-023
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Dashboard for logged-in users to view and revisit saved analyses.

## Acceptance Criteria
- List sorted by date — most recent first
- Each item: document type icon, type, language pair, date
- Search bar filters by type or date
- Filter chips: All, Rental, Employment, Freelance, Other
- Empty state with upload CTA
- Tap item opens full analysis
- Usage bar shows analyses used vs plan limit
- Free tier limit hit: upgrade banner at top
BODY_END
gi 'CLR-023 | Build user dashboard with analysis history (SCR-11)' 'epic-4-results,sprint-4,P1-high,size-M,type-feature' 'Sprint 4 Accounts+Growth'

# CLR-024
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Account page with preferences and one-click full data deletion.

## Acceptance Criteria
- Shows: email, subscription tier, member since, language preferences
- Language preferences editable and saved immediately
- Delete account: requires typing DELETE to confirm
- Deletion removes: PostgreSQL record, Clerk account, all saved analyses
- Deletion completes within 30 seconds — fully automated
- GDPR data export: download all stored data as JSON
- Deletion is complete and immediate — GDPR legal requirement
BODY_END
gi 'CLR-024 | Build account settings and GDPR data deletion' 'epic-4-results,sprint-4,P1-high,size-M,type-feature' 'Sprint 4 Accounts+Growth'

# CLR-025
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
2 lifetime free analyses. Upgrade prompts shown after value is demonstrated.

## Acceptance Criteria
- Count tracked per user in PostgreSQL
- Anonymous: count in localStorage and by IP
- Before upload if exhausted: show pricing page
- First free analysis: no prompt shown
- Second analysis results: upgrade prompt only after scrolling past 2 clauses
- Free exhausted: You have used both free analyses. Upgrade to continue.
- Unlimited plan: no count shown
- Upgrade prompt must never appear before user has seen value
BODY_END
gi 'CLR-025 | Build free tier quota tracking and upgrade prompts' 'epic-4-results,sprint-3,P0-critical,size-M,type-feature' 'Sprint 3 Results+Payments'

# CLR-026
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Stripe for subscription billing. All four plans. Monthly and annual variants.

## Acceptance Criteria
- Four products: Free, Starter $7/mo, Pro $19/mo, Team $49/mo
- Annual variants at 25% discount
- Webhooks: payment succeeded, failed, subscription cancelled, updated
- Webhooks secured with Stripe signature verification
- Subscription status synced to PostgreSQL on every webhook
- Failed payment: 3-day grace period before downgrade
- Stripe API key in AWS Secrets Manager
- No card data ever touches Clairo servers (Stripe handles all)
BODY_END
gi 'CLR-026 | Set up Stripe subscription billing with all four tiers' 'epic-5-payments,sprint-3,P0-critical,size-L,type-infrastructure' 'Sprint 3 Results+Payments'

# CLR-027
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Clean honest pricing. No dark patterns. Monthly/annual toggle. Comparison table.

## Acceptance Criteria
- Four plan cards clearly displayed
- Monthly/annual toggle with 25% off shown for annual
- Pro highlighted as Most popular
- Full feature comparison table below cards
- FAQ section with 7 questions
- No fake countdown timers, no artificial scarcity, no dark patterns
- No credit card required stated on free card
- Cancel any time stated clearly
BODY_END
gi 'CLR-027 | Build pricing page (SCR-10)' 'epic-5-payments,sprint-3,P0-critical,size-M,type-feature' 'Sprint 3 Results+Payments'

# CLR-028
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
From clicking upgrade to completed subscription using Stripe Checkout.

## Acceptance Criteria
- Upgrade redirects to Stripe Checkout (hosted by Stripe — no card data on our side)
- Success URL returns to dashboard with subscription active
- Subscription active within 30 seconds
- Confirmation email from Stripe automatically
- Upgrade from Starter to Pro prorated correctly
BODY_END
gi 'CLR-028 | Build subscription upgrade and checkout flow' 'epic-5-payments,sprint-4,P1-high,size-M,type-feature' 'Sprint 4 Accounts+Growth'

# CLR-029
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Users manage, downgrade, or cancel subscription from account settings.

## Acceptance Criteria
- Current plan visible with renewal date
- Change plan: prorated, applied immediately
- Cancel: two-step confirmation, access until period end
- Cancelled users downgraded to free at period end
- Reactivate available after cancellation
- Billing history with downloadable invoices
BODY_END
gi 'CLR-029 | Build subscription management and cancellation' 'epic-5-payments,sprint-4,P1-high,size-M,type-feature' 'Sprint 4 Accounts+Growth'

# CLR-030
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Redis-based rate limiting on every endpoint. Prevents API cost abuse.

## Acceptance Criteria
- Upload: 3 requests/hour anonymous, 20/hour paid
- Auth: 10 attempts/hour per IP before temp block
- Rate limit headers on every response
- 429 with Retry-After when exceeded
- Counters in Redis with TTL
- Sentry alert if any IP exceeds 50 requests/hour
BODY_END
gi 'CLR-030 | Implement rate limiting on all API endpoints' 'epic-6-accounts,sprint-2,P0-critical,size-M,type-security' 'Sprint 2 Upload+AI'

# CLR-031
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
JWT verification on all protected routes.

## Acceptance Criteria
- JWT middleware on all protected routes
- Signature verified using Clerk public key
- Expired tokens return 401
- Public routes exempt: landing, pricing, shared links, health
- Upload accepts authenticated and anonymous (rate limiting applied to both)
- 401 responses contain no system information
- Failures logged (IP and timestamp only — no user data)
BODY_END
gi 'CLR-031 | Implement JWT authentication middleware' 'epic-6-accounts,sprint-2,P0-critical,size-M,type-security' 'Sprint 2 Upload+AI'

# CLR-032
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Documents never touch persistent storage. Purged at every exit point.

## Acceptance Criteria
- Processing in isolated AWS Lambda with no write access to persistent storage
- Document variable explicitly deleted after each step
- On success: deleted before response returned
- On error: deleted before error response returned
- On timeout: Lambda terminated, memory cleared by AWS
- Integration test: no document content in any log, DB, or cache after analysis
- This test runs before every production deployment
- MOST CRITICAL security requirement
BODY_END
gi 'CLR-032 | Implement document memory isolation and purge guarantee' 'epic-6-accounts,sprint-2,P0-critical,size-M,type-security' 'Sprint 2 Upload+AI'

# CLR-033
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Malicious instructions in documents cannot override Claude's system prompt.

## Acceptance Criteria
- Document content as user message data only — never system message
- System prompt instructs Claude to treat document as data not instructions
- Claude response validated as strict JSON — non-matching discarded
- 20 injection attempts in test suite — all must fail
- Schema validation before any Claude response shown to user
- Test suite re-run on every system prompt change
BODY_END
gi 'CLR-033 | Implement prompt injection protection' 'epic-6-accounts,sprint-2,P0-critical,size-M,type-security' 'Sprint 2 Upload+AI'

# CLR-034
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
All security HTTP headers. Must achieve A+ on securityheaders.com.

## Acceptance Criteria
- HTTPS enforced — HTTP redirects to HTTPS
- HSTS: max-age=31536000; includeSubDomains
- Content-Security-Policy configured
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: restricts camera to specific pages only
- securityheaders.com grade: A+
- CORS: only clairo.app and localhost:3000
BODY_END
gi 'CLR-034 | Set up security headers and HTTPS enforcement' 'epic-6-accounts,sprint-1,P0-critical,size-S,type-security' 'Sprint 1 Foundation'

# CLR-035
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
All API keys in Secrets Manager. Never in code or committed files.

## Acceptance Criteria
- Secrets: ANTHROPIC_API_KEY, GOOGLE_VISION_KEY, STRIPE_SECRET_KEY, CLERK_SECRET_KEY, DATABASE_URL
- Backend retrieves from Secrets Manager at startup only
- IAM role: read-only access to specific secrets only
- Git secret scanning: committed keys block the push
- Rotation policy: 90 days
- .env.local.example with placeholders only
BODY_END
gi 'CLR-035 | Set up API key management with AWS Secrets Manager' 'epic-6-accounts,sprint-1,P0-critical,size-M,type-security' 'Sprint 1 Foundation'

# CLR-036
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Non-dismissable disclaimer on every analysis screen. Translated into output language.

## Acceptance Criteria
- Renders above every analysis result
- Text: This analysis explains what your document says. It is not legal advice. Analysis date: [DATE].
- Cannot be dismissed, hidden, or scrolled away — sticky
- Background: danger-100, left border danger-700 3px
- Date dynamically inserted
- Translated into all 8 languages AND user's output language
- Legal advisor approved exact wording
- Minimum font size 13px
- Cannot be A/B tested or modified without legal review
BODY_END
gi 'CLR-036 | Build permanent legal disclaimer component' 'epic-7-growth,sprint-2,P0-critical,size-S,type-legal' 'Sprint 2 Upload+AI'

# CLR-037
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Country and document-type specific professional referrals at bottom of results.

## Acceptance Criteria
- Renders at bottom of every analysis results screen
- Germany + rental: Mieterverein
- UK + rental: Citizens Advice
- UK + employment: ACAS
- US + any: State Bar Association referral
- UAE + employment: UAE Ministry of Human Resources
- India + any: National Legal Services Authority
- Fallback: generic bar association for country
- All links open in new tab and verified working before launch
- Translated into output language
BODY_END
gi 'CLR-037 | Build Find a Professional component with country-specific referrals' 'epic-7-growth,sprint-3,P0-critical,size-M,type-legal' 'Sprint 3 Results+Payments'

# CLR-038
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Full block shown when prohibited document detected. No partial analysis ever shown.

## Acceptance Criteria
- Shown when CLR-013 detects prohibited type
- Clear message with type explanation
- Specific referral: court order -> legal aid, immigration -> UNHCR, medical -> patient advocacy
- No partial analysis shown
- Free analysis count NOT decremented
- Legal advisor reviewed all messages and referrals
BODY_END
gi 'CLR-038 | Build prohibited document type blocking screen' 'epic-7-growth,sprint-2,P0-critical,size-S,type-legal' 'Sprint 2 Upload+AI'

# CLR-039
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Plain English Privacy Policy and TOS. Must exist before any user touches the product.

## Acceptance Criteria
- Privacy Policy at /privacy: data collected, document deletion, user rights GDPR/CCPA
- Terms of Service at /terms: what Clairo is/isn't, not legal advice, prohibited docs, liability
- Both reviewed and approved in writing by a qualified lawyer
- Linked from: footer, trust screen, account settings
- Last updated date shown
- HARD BLOCKER: neither page goes live without written lawyer approval
BODY_END
gi 'CLR-039 | Build privacy policy and terms of service pages' 'epic-7-growth,sprint-2,P0-critical,size-M,type-legal' 'Sprint 2 Upload+AI'

# CLR-040
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Every number in clause explanations links to source text for verification.

## Acceptance Criteria
- Every number in explanations is a tappable link
- Tap: source text panel opens with that number highlighted
- Static warning: Please verify all dates, amounts, and time periods against your original document
- Warning more prominent for camera/image uploads
- Covers: currency, percentages, days/weeks/months/years, dates
- Legal advisor reviewed warning text
BODY_END
gi 'CLR-040 | Build OCR number verification warning system' 'epic-7-growth,sprint-2,P0-critical,size-S,type-legal' 'Sprint 2 Upload+AI'

# CLR-041
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Unique public links showing explanations only — never original document content.

## Acceptance Criteria
- Share button generates clairo.app/s/[uuid]
- Stored: analysis_id, created_at, expires_at (30 days), is_revoked
- Link serves ONLY: summary, clause explanations, flags, frequency stats, disclaimer
- Link NEVER serves: original document text, extracted OCR text, user identity
- noindex meta tag on all shared pages
- Auto-expires after 30 days
- User can revoke instantly
- Rate limiting: 100 views/hour per link
BODY_END
gi 'CLR-041 | Build shareable analysis link generation' 'epic-8-quality,sprint-3,P0-critical,size-M,type-feature' 'Sprint 3 Results+Payments'

# CLR-042
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Public page at /s/[shareId]. Drives new signups through viral loop.

## Acceptance Criteria
- Renders at /s/[shareId]
- Shows: type, language pair, date, disclaimer, summary, clause cards
- Does NOT show: original document, extracted text, user identity
- Source text toggle hidden on shared pages
- Sticky CTA: Understand your own contract in 60 seconds — Try Clairo free
- Expired link: clear message + upload CTA
- Revoked shows same as expired (no difference — prevents enumeration)
- Open Graph meta tags for rich WhatsApp preview
- noindex meta tag
BODY_END
gi 'CLR-042 | Build shared analysis public page (SCR-09)' 'epic-8-quality,sprint-3,P0-critical,size-M,type-feature' 'Sprint 3 Results+Payments'

# CLR-043
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Custom share sheet with WhatsApp as primary. Expat communities share on WhatsApp.

## Acceptance Criteria
- Custom share sheet (not just native device share)
- WhatsApp shown first and largest — primary action
- WhatsApp message: summary sentence + link
- Copy link second
- Native share as More options
- Share count tracked in analytics
BODY_END
gi 'CLR-043 | Build WhatsApp-first share sheet' 'epic-8-quality,sprint-4,P1-high,size-S,type-feature' 'Sprint 4 Accounts+Growth'

# CLR-044
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Give a friend one free analysis, get one free yourself.

## Acceptance Criteria
- Referral link per user: clairo.app/ref/[userId]
- Both users get 1 bonus analysis when friend completes first analysis
- Bonus added only after friend's first analysis (not just signup)
- Maximum 10 referral bonuses per user
- Referral stats in account settings
- Bonus analyses do not expire
BODY_END
gi 'CLR-044 | Build referral programme' 'epic-8-quality,sprint-4,P1-high,size-M,type-feature' 'Sprint 4 Accounts+Growth'

# CLR-045
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Product analytics. No document content, no PII in any event.

## Acceptance Criteria
- PostHog self-hosted on AWS
- Events: page_view, upload_started, upload_completed, analysis_started, analysis_completed, analysis_shared, upgrade_prompted, upgrade_completed
- No document content in any event
- No PII — anonymous user ID only
- Funnel: landing -> upload -> analysis -> upgrade
- Cookie consent banner — analytics starts only after consent
- User can opt out in account settings
BODY_END
gi 'CLR-045 | Set up PostHog analytics with privacy-safe event tracking' 'epic-9-security,sprint-3,P0-critical,size-M,type-infrastructure' 'Sprint 3 Results+Payments'

# CLR-046
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Mobile-first landing page. Converts visitors. Animated demo. Trust signals above fold.

## Acceptance Criteria
- Hero: headline, subheadline, animated demo, primary CTA
- Animated demo: CSS/SVG animation — no video, no sound, loops
- Trust strip: 3 signals visible without scrolling on 375px screen
- How it works: 3 steps with icons
- Use case cards: renter, job switcher, expat
- Language showcase: rotating banner (German to Hindi, English to Arabic, French to Urdu)
- Pricing teaser: 3 plan cards
- Lighthouse performance > 90 on mobile
- Page loads under 2 seconds on 4G
- Localised: German examples for Germany, UK examples for UK
- All strings in i18n files
BODY_END
gi 'CLR-046 | Build landing page (SCR-01)' 'epic-9-security,sprint-3,P0-critical,size-L,type-feature' 'Sprint 3 Results+Payments'

# CLR-047
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Helpful error pages. No technical details exposed to users.

## Acceptance Criteria
- 404: friendly message, link home, upload CTA
- 500: apology, confirmation no document stored, link home
- Both styled with Clairo design system
- Both translated into interface language
- No technical error details shown
- Sentry captures 500 errors automatically
BODY_END
gi 'CLR-047 | Build 404 and error pages' 'epic-9-security,sprint-3,P0-critical,size-S,type-feature' 'Sprint 3 Results+Payments'

# CLR-048
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
View previous analyses offline. Critical for expats with poor internet at signing time.

## Acceptance Criteria
- Service worker caches analysis results for logged-in users
- Offline view shows: You are viewing a cached version from [date]
- New uploads not permitted offline — clear message
- Cache updates when connection restored
- Cache limited to 10 most recent analyses
- User can clear cache in account settings
- PWA install prompt after 3 visits
BODY_END
gi 'CLR-048 | Build offline mode for cached analyses' 'epic-9-security,sprint-5,P1-high,size-M,type-feature' 'Sprint 5 Quality+Security'

# CLR-049
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Country-specific landing pages with local examples and local currency.

## Acceptance Criteria
- Country detected from IP geolocation
- /de: German lease example, Mieterverein reference, prices in EUR
- /uk: UK tenancy example, Citizens Advice reference, prices in GBP
- /in: Indian employment example, prices in INR
- /ae: UAE employment example, prices in AED
- Global English fallback for all other countries
- hreflang tags for SEO
BODY_END
gi 'CLR-049 | Build localised landing pages by country' 'epic-9-security,sprint-6,P2-roadmap,size-L,type-feature' 'Sprint 6 Launch'

# CLR-050
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
All performance targets from Frontend Spec. Measured on real device.

## Acceptance Criteria
- Landing page Lighthouse performance > 90 on mobile
- First Contentful Paint < 1.5 seconds on 4G
- Largest Contentful Paint < 2.5 seconds on 4G
- All images in WebP format
- JS bundle split — load only what each page needs
- Results screen paint after analysis < 500ms
- Measured on real device not Chrome DevTools simulation
BODY_END
gi 'CLR-050 | Performance optimisation — meet all Lighthouse targets' 'epic-10-launch,sprint-5,P0-critical,size-M,type-infrastructure' 'Sprint 5 Quality+Security'

# CLR-051
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Full audit of all 11 core screens with real screen readers.

## Acceptance Criteria
- axe-core audit: zero critical violations on all screens
- Keyboard navigation: every action completable without mouse
- iOS VoiceOver: all screens navigable
- Android TalkBack: all screens navigable
- Color contrast: all text/background 4.5:1 minimum
- All images have alt text
- prefers-reduced-motion: all animations disabled
- RTL verified on real device in Arabic and Urdu
BODY_END
gi 'CLR-051 | Accessibility audit — WCAG 2.1 AA compliance' 'epic-10-launch,sprint-5,P0-critical,size-M,type-infrastructure' 'Sprint 5 Quality+Security'

# CLR-052
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
All core flows tested on real devices and browsers for Clairo's target market.

## Acceptance Criteria
- Chrome Android, Safari iOS, Chrome Desktop, Safari Desktop, Firefox Desktop
- iPhone 12, iPhone 15 Pro, Samsung Galaxy S22, iPad
- Camera capture tested on real iOS and Android
- HEIC upload tested on iPhone
- RTL tested on device with Arabic system language
- All 11 screens verified on each combination
- All failures fixed before launch
BODY_END
gi 'CLR-052 | Cross-browser and cross-device testing' 'epic-10-launch,sprint-5,P0-critical,size-M,type-infrastructure' 'Sprint 5 Quality+Security'

# CLR-053
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
External pen test before launch. Non-negotiable for a product handling legal documents.

## Acceptance Criteria
- Security firm engaged by end of Sprint 4
- Scope: upload, analysis, auth, shared links, rate limiting, prompt injection
- All Critical and High findings fixed before launch
- Medium findings triaged with written rationale
- Firm re-tests all fixed findings
- NDA signed before sharing technical details
- Budget minimum $3,000
- HARD BLOCKER: cannot launch without completed pen test
BODY_END
gi 'CLR-053 | Independent security penetration test' 'epic-10-launch,sprint-5,P0-critical,size-L,type-security' 'Sprint 5 Quality+Security'

# CLR-054
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Automated E2E tests for all critical flows. Runs before every production deployment.

## Acceptance Criteria
- Playwright configured
- Flows: PDF upload -> analysis, camera -> OCR review -> analysis, free tier limits, shared link, prohibited doc blocking, signup -> upload -> analysis
- Tests run before every production deployment
- All must pass before deploy to production
- No document content in test fixtures — synthetic docs only
- Analysis completes under 60 seconds in test environment
BODY_END
gi 'CLR-054 | End-to-end integration test suite with Playwright' 'epic-10-launch,sprint-5,P0-critical,size-L,type-infrastructure' 'Sprint 5 Quality+Security'

# CLR-055
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
All GDPR requirements before EU launch.

## Acceptance Criteria
- Cookie consent banner with granular options
- Analytics starts only after explicit consent
- GET /api/user/export returns all stored user data as JSON
- DELETE /api/user completes within 30 seconds
- Processing register documented
- Privacy Policy has GDPR rights section
- DPO contact in Privacy Policy
- Zero document retention documented as GDPR compliance measure
- GDPR assessment reviewed by legal advisor
- HARD BLOCKER for EU launch
BODY_END
gi 'CLR-055 | GDPR compliance implementation' 'epic-10-launch,sprint-5,P0-critical,size-M,type-legal' 'Sprint 5 Quality+Security'

# CLR-056
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Real-time monitoring so team knows immediately if anything goes wrong.

## Acceptance Criteria
- Sentry: alert on error rate > 1% within 5-minute window
- Uptime monitoring: alert if non-200 for 2+ consecutive checks
- Cost alert: AWS + Anthropic at 120% of expected daily budget
- DB connection alert if pool exhausted
- Rate limit abuse: alert if IP hits 50+ requests/hour
- Claude API alert: 3+ consecutive errors
- Alert channels: Slack primary, email backup
- On-call rotation documented
- Runbook for each alert type
BODY_END
gi 'CLR-056 | Monitoring, alerting and on-call setup' 'epic-10-launch,sprint-6,P0-critical,size-M,type-infrastructure' 'Sprint 6 Launch'

# CLR-057
cat > /tmp/_clairo_body.md << 'BODY_END'
## Description
Final checklist. Every item checked by a named person before launch.

## Acceptance Criteria
- Privacy Policy: lawyer approved, live at /privacy
- Terms of Service: lawyer approved, live at /terms
- Legal disclaimer: lawyer approved, on all analysis screens
- System prompt: lawyer approved, version controlled
- Prohibited document list: lawyer approved
- Professional referral links: all verified working
- Security pen test: completed, all Critical/High resolved
- GDPR: legal advisor approved
- All P0 tickets done and verified on staging
- E2E tests: all passing on staging
- Lighthouse > 90 on mobile
- WCAG 2.1 AA passed
- Monitoring and alerting configured and tested
- Stripe test payments working end-to-end
- API keys: all in Secrets Manager, none in code
- No document content in any log
- No document content columns in database schema
- CEO, CTO, Legal Advisor all sign the checklist
- HARD BLOCKER: 100% complete before any public traffic
BODY_END
gi 'CLR-057 | Pre-launch checklist and go-live procedure' 'epic-10-launch,sprint-6,P0-critical,size-M,type-infrastructure' 'Sprint 6 Launch'


echo ""
echo "Done! View at: https://github.com/$FULL_REPO"
