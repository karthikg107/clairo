# Contributing to Clairo

## Branching

```
main          ← production
staging       ← pre-production
dev           ← integration
feature/CLR-XXX-short-description
fix/CLR-XXX-short-description
```

- Branch from `dev`
- PR into `dev`
- Never push directly to `main` or `staging`

## Commit Convention

```
<type>(<scope>): <subject>

Types: feat | fix | chore | docs | style | refactor | test | perf | ci
```

Examples:
```
feat(upload): add PDF drag-and-drop component
fix(i18n): correct Arabic RTL margin override
chore(deps): bump next-intl to 3.18.0
```

## Pull Request Checklist

- [ ] Linked to a GitHub issue (CLR-XXX)
- [ ] `pnpm lint` passes
- [ ] `pnpm type-check` passes
- [ ] Mobile-first at 375px (design system)
- [ ] WCAG 2.1 AA: keyboard nav, focus-visible, 48px touch targets
- [ ] RTL tested if UI changed (ar, ur locales)
- [ ] No document content in logs, DB, or cache
- [ ] Translation keys added for all 8 locales if new UI copy

## Design System

| Token | Value |
|-------|-------|
| Brand | #1B4F8A |
| Accent | #E85D2F |
| Success | #1A7A4A |
| Warning | #B36200 |
| Danger | #B91C1C |
| Background | #F8FAFC |
| Dark text | #1A1A2E |

Components must use Tailwind classes from `tailwind.config.ts`. No hardcoded hex values in component files.

## Security Rules (non-negotiable)

1. **No document content** in logs, DB columns, Redis, or error messages
2. **No secrets** in code or `.env.local` committed to git
3. **Legal disclaimer** must be non-dismissable wherever documents are handled
4. **OCR review screen** cannot be skipped — user must confirm extracted text

## Running Checks Locally

```bash
pnpm lint          # ESLint + jsx-a11y
pnpm type-check    # TypeScript strict
```

Pre-commit hooks (Husky + lint-staged) run automatically on `git commit`.
