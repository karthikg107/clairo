# Clerk Security Configuration (auth-layer hardening)

> **HUMAN ACTION REQUIRED — Clerk dashboard.** Clairo delegates _all_
> authentication to Clerk. There is no login, password, session, or
> refresh-token code in this repo (verified: zero login endpoints in
> `backend/app/api`). The security controls below therefore **cannot be
> implemented in our codebase** — building them here would be code that
> never runs during login. Configure each in the Clerk Dashboard before
> launch. This document is the mapping from the security-hardening spec to
> the exact Clerk setting.

## Why these live in Clerk, not our code

A login attempt hits **Clerk's infrastructure** (the hosted `<SignIn>` /
`<SignUp>` components post to `*.clerk.accounts.dev`), issues a Clerk
session, and returns a short-lived JWT. Our backend only ever _verifies_
that JWT (signature, `exp`, `iss`, `aud`, `nbf` — see
`app/middleware/jwt_auth.py`). So login rate limiting, lockout, brute-force
backoff, refresh rotation, and concurrent-session caps are all enforced by
Clerk, upstream of us.

## Required Clerk Dashboard settings

| Spec item                                     | Clerk Dashboard setting                                                                     | Target value                                                                                                |
| --------------------------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 1 — Login rate limiting (5 fails/IP/min)      | **User & Authentication → Attack protection → Rate limiting** (enabled by default on Clerk) | Keep enabled; Clerk enforces per-IP sign-in throttling                                                      |
| 1 — Account lockout after repeated failures   | **Attack protection → Account lockout**                                                     | Enable; max failed attempts = **10**, lockout duration per policy                                           |
| 1 — Unlock email sent automatically           | **Account lockout → Lockout duration / self-service unlock** + **Emails**                   | Enable self-service unlock email                                                                            |
| 3 — Brute-force backoff (15 min → 1 h → 24 h) | **Attack protection → Account lockout** (progressive) + **Bot protection**                  | Enable bot protection (CAPTCHA); set escalating lockout durations                                           |
| 6 — JWT/session token lifetime                | **Sessions → Token lifetime**                                                               | Session token (JWT) short-lived (Clerk default 60 s); **inactivity timeout ≤ 1 h**, max lifetime per policy |
| 6 — Refresh-token rotation on every use       | Automatic in Clerk (session tokens are minted from the rotating Clerk session)              | No action — Clerk rotates by design                                                                         |
| 6 — Max 5 concurrent sessions per user        | **Sessions → Multi-session handling / active session limit**                                | Set active session limit = **5**                                                                            |
| 8 — Honeypot / bot protection on signup       | **Attack protection → Bot protection**                                                      | Enable CAPTCHA/bot detection (replaces a honeypot on the Clerk-hosted form)                                 |

## What our codebase DOES do at the auth boundary

Even though enforcement is Clerk's, we harden and observe our own surface:

- **JWT verification** (`app/middleware/jwt_auth.py`): rejects expired,
  tampered, wrong-issuer, and malformed tokens (tests in
  `tests/test_jwt_auth.py`).
- **API auth-failure monitoring** (this hardening pass): every
  invalid-token 401 is counted per-IP in Redis and written to `audit_log`;
  a **Sentry alert fires at >10 invalid-token 401s from one IP in 5 min**
  (`record_auth_failure` + `_note_auth_failure`). This is the honest analog
  of "login attempt monitoring" for the surface we actually control.
- **Session revocation on account deletion**: deleting an account calls
  Clerk to delete the user, revoking all their sessions
  (`app/services/clerk.py`, wired into `POST /api/v1/account/delete`).
  Requires `CLERK_SECRET_KEY` in the backend environment.

## Optional follow-up — login events into our audit_log

To get Clerk's _login_ events (success/fail/lockout) into our unified
`audit_log`, add a **Clerk webhook** (Dashboard → Webhooks) for
`session.created`, `session.ended`, and user lockout events, pointing at a
new signed endpoint (`POST /api/v1/clerk/webhook`, Svix-signature verified).
Not built in this pass because it can't be exercised without live Clerk
webhook configuration; scoped here as the next step if unified login
logging is required for compliance.
