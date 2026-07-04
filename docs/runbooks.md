# Alert Runbooks (CLR-056)

One runbook per alert type. Every alert lands in Slack `#clairo-alerts`
(primary) and `oncall@clairo.app` (backup). Severity levels: **P1** =
users can't use the product, act now; **P2** = degraded, act within the
hour; **P3** = investigate within the day.

---

## 1. Analysis error rate >1% (5-minute window) — P1

**Signal:** Sentry message `Claude API error rate X% exceeds 1% threshold`
(emitted by `backend/app/core/circuit_breaker.py`).

**What it means:** more than 1 in 100 analysis attempts is failing —
users are seeing the "analysis unavailable" screen.

**First checks (in order):**

1. Sentry → most recent backend exceptions: is one error type dominating?
2. Anthropic status page (status.anthropic.com) — provider outage?
3. `GET /api/v1/ready` — is it a DB/Redis problem masquerading as
   analysis failures?
4. Grep structured logs for `analysis.` events around the alert window.

**Remediation:**

- Provider outage → nothing to fix server-side; the circuit breaker
  limits damage. Post a status update if sustained >15 min.
- Bad deploy correlation → roll back to the previous release.
- Malformed-response spike (`analysis_failed` 422s) → check whether a
  model change altered output; the JSON-correction retry should absorb
  singletons, a spike means the schema drifted — pin/adjust the prompt.

**Escalation:** if error rate stays >1% for 30 minutes → page the
engineering lead.

---

## 2. Claude API: 3 consecutive errors — P2

**Signal:** Sentry message `Claude API: 3 consecutive errors`.

**What it means:** an early tremor — three analysis calls in a row
failed. Often precedes runbook #1 or #3 firing.

**First checks:** same as runbook #1, steps 1–2. Also check whether the
errors share one user/document type (single bad input, not an outage).

**Remediation:** usually none needed if isolated — the alert fires once
per streak by design. Two streak alerts within 15 minutes → treat as
runbook #1.

---

## 3. Circuit breaker opened — P1

**Signal:** Sentry message `Claude API circuit breaker opened after N
failures/min`; log event `circuit_breaker.opened`.

**What it means:** 5 analysis failures within a minute; ALL analyses are
paused for 60 seconds (users get a clear "temporarily unavailable"
message, and their quota is never consumed for failed attempts).

**First checks:** Anthropic status page; Sentry exception types;
`ANTHROPIC_API_KEY` validity (expired/rotated key looks exactly like
this).

**Remediation:**

- Provider outage → breaker will keep cycling; post a status update.
- Auth errors → rotate/fix the key in Secrets Manager (`clairo/anthropic`).
- Repeated open/close cycling >10 min → page the engineering lead.

---

## 4. Rate-limit abuse: identifier at 50+ requests/hour — P3

**Signal:** Sentry message `Rate limit alert: <id> hit N req/hr on
/<endpoint>` (emitted by `backend/app/core/rate_limit.py`).

**What it means:** a single IP/user is hammering an endpoint — scraping,
a bot, or a stuck client. Limits are already enforcing (429s); this is
awareness, not breakage.

**First checks:**

1. Which endpoint? `/upload` abuse costs OCR money — prioritize.
   `/shared` is per-link limited separately (100/hr/link).
2. One identifier or many? Many IPs at threshold simultaneously =
   coordinated — treat as P2.

**Remediation:**

- Single stuck client → nothing; limits hold.
- Sustained/hostile → block the IP at the CDN/WAF level.
- Legitimate integration → talk to the user; consider a higher tier.

---

## 5. Uptime check failing — P1

**Signal:** uptime provider alert (2 consecutive failures) for
landing / api-health / api-ready.

**First checks:**

1. Which check? `landing` down + `api-health` up = frontend/hosting.
   `api-health` down = backend. `api-ready` down alone = DB or Redis.
2. Hosting provider status pages (Vercel/AWS).
3. Recent deploys — correlate timestamps.

**Remediation:**

- Frontend down → check hosting dashboard, roll back last deploy.
- Backend down → check container/instance health, restart, roll back.
- `api-ready` only → check RDS / ElastiCache health and connection
  counts; the fail-open design keeps analyses working through SHORT
  Redis blips, but DB loss breaks auth'd endpoints.
- Post a public status update if user-facing >10 min.

---

## 6. Cost alert: 120% of expected daily budget — P2

**Signal:** AWS Budgets email/SNS, or Anthropic console limit email.

**First checks:**

1. AWS Cost Explorer → which service jumped (usually OCR calls or
   RDS/data transfer)?
2. Anthropic console usage → correlate with analysis volume; check the
   cache hit rate in logs (`analysis_cache_hit`) — a cache regression
   doubles Claude spend silently.
3. Cross-reference the rate-limit abuse alert (#4): abuse and cost
   spikes usually arrive together.

**Remediation:**

- Legitimate growth → raise the budget, celebrate.
- Cache regression → check Redis health / cache-key changes.
- Abuse → block at WAF; verify quotas and per-endpoint limits are
  actually returning 429s.

**Escalation:** >200% of daily budget → engineering lead immediately;
consider temporarily lowering rate limits.
