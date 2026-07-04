# Monitoring & Alerting (CLR-056)

Alert **channels: Slack `#clairo-alerts` primary, email backup** — every
alert below routes to both (Slack via integration, email as fallback for
Slack outages). Runbooks for every alert live in
[`docs/runbooks.md`](../docs/runbooks.md).

## What fires alerts (implemented in code)

All application alerts are emitted as Sentry messages by the backend —
Sentry then fans out to Slack + email via the alert rules below.

| Alert                     | Trigger                                                    | Emitted from                                                                |
| ------------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------- |
| Analysis error rate       | >1% errors over a rolling 5-minute window (min 20 samples) | `backend/app/core/circuit_breaker.py` (`analysis.error_rate_alert`)         |
| Claude consecutive errors | 3 Claude errors in a row, once per streak                  | `backend/app/core/circuit_breaker.py` (`analysis.consecutive_errors_alert`) |
| Circuit breaker opened    | 5 analysis failures within 60s → 60s pause                 | `backend/app/core/circuit_breaker.py` (`circuit_breaker.opened`)            |
| Rate-limit abuse          | Any identifier crosses 50 requests/hour on any endpoint    | `backend/app/middleware/rate_limit.py` / `app/core/rate_limit.py`           |
| Unhandled exceptions      | Any uncaught backend error                                 | `sentry_sdk.init` in `backend/app/main.py` (set `SENTRY_DSN`)               |

## Sentry alert rules — apply once per environment

In Sentry → Alerts → Create Alert (or via `sentry-cli`/API), create:

1. **Issue alert — "Backend errors"**
   - When: an event is seen, `level:error`
   - Then: notify Slack `#clairo-alerts` AND email `oncall@clairo.app`
2. **Metric alert — "Error rate >1% / 5min"**
   - Dataset: events; query `event.type:error`; window 5 minutes
   - Critical threshold: >1% of transaction volume (or count-based
     equivalent for the plan tier)
   - Actions: Slack primary, email backup
   - Note: the application ALSO computes this internally and emits
     `analysis.error_rate_alert` — belt and suspenders; keep both.
3. **Issue alert — "Operational alerts"**
   - When: message matches `circuit breaker opened` OR `consecutive
errors` OR `Rate limit alert`
   - Then: Slack `#clairo-alerts` + email

## Uptime monitoring

Definitions in [`uptime-checks.yml`](./uptime-checks.yml) — apply to any
provider (Checkly, BetterStack, UptimeRobot). Checks:

- `GET https://clairo.app/` — landing must return 200, contain
  `Understand any contract`, TLS valid; every 60s from EU + US + APAC.
- `GET https://api.clairo.app/api/v1/health` — 200 `{"status":"ok"}`;
  every 60s.
- `GET https://api.clairo.app/api/v1/ready` — 200 (DB + Redis
  reachable); every 5 min.

Alert after 2 consecutive failures → Slack primary, email backup.

## Cost alerts (120% of expected daily budget)

- **AWS**: `aws-budget.json` in this directory —
  `aws budgets create-budget --account-id <ID> --budget file://monitoring/aws-budget.json --notifications-with-subscribers file://monitoring/aws-budget-notifications.json`
  after replacing the placeholder amount/emails. Budget is DAILY cost;
  notification threshold 120% of budgeted amount (both ACTUAL and
  FORECASTED).
- **Anthropic (Claude API)**: set a monthly spend limit + email alert at
  120% of (expected daily budget × days in month) in the Anthropic
  Console → Billing → Limits. There is no public API for this — it is a
  console setting. **[HUMAN ACTION REQUIRED]**
- **Stripe/Clerk/PostHog**: fixed-tier pricing — review monthly, no
  automated alert needed at current scale.

## What still needs a human

- Create the Sentry project & set `SENTRY_DSN` in backend secrets.
- Install the Sentry Slack integration and pick `#clairo-alerts`.
- Create the uptime checks at the chosen provider from
  `uptime-checks.yml`.
- Run the AWS budget CLI commands with the real account id, amount, and
  SNS/email targets.
- Set the Anthropic console spend limit.
