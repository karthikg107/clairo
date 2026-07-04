# GDPR Processing Register (Art. 30 GDPR)

> **Status: DRAFT — requires legal review before launch.**
> Controller details, DPO designation, and transfer-mechanism entries
> marked **[LEGAL REVIEW REQUIRED]** must be completed/approved by
> counsel. This register documents what the codebase actually does as of
> CLR-055; keep it in sync with schema and processor changes.

**Controller:** Clairo **[LEGAL REVIEW REQUIRED — legal entity name, address, contact]**
**DPO / privacy contact:** **[LEGAL REVIEW REQUIRED]**

---

## 1. Processing activities

### 1.1 Contract analysis (core service)

|                     |                                                                                                                                                                                                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Purpose**         | Explain a user's uploaded contract in plain language                                                                                                                                                                                                          |
| **Legal basis**     | Contract performance (Art. 6(1)(b))                                                                                                                                                                                                                           |
| **Data subjects**   | Users (signed-in and anonymous)                                                                                                                                                                                                                               |
| **Data categories** | Document text (transient), document metadata (type, language), AI-generated analysis output                                                                                                                                                                   |
| **Recipients**      | Anthropic (AI analysis — zero data retention configured), Google Cloud Vision / AWS Textract (OCR)                                                                                                                                                            |
| **Retention**       | Document text: **never stored** — processed in memory, purged immediately after analysis (all error paths included). Analysis output (structured JSON, no document text beyond ≤200-char clause excerpts): stored for signed-in users until account deletion. |
| **Transfers**       | **[LEGAL REVIEW REQUIRED — confirm processor regions + SCCs/DPAs for Anthropic, Google, AWS]**                                                                                                                                                                |

### 1.2 Account management

|                     |                                                                                                           |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| **Purpose**         | Authentication, account settings, quota tracking                                                          |
| **Legal basis**     | Contract performance (Art. 6(1)(b))                                                                       |
| **Data categories** | Email, Clerk user id, ToS acceptance, language preferences, country, usage counters (free/bonus analyses) |
| **Recipients**      | Clerk (authentication processor)                                                                          |
| **Retention**       | Until account deletion (immediate hard delete — see §3)                                                   |

### 1.3 Payments

|                     |                                                                                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Purpose**         | Subscription billing                                                                                                                             |
| **Legal basis**     | Contract performance (Art. 6(1)(b))                                                                                                              |
| **Data categories** | Subscription tier/status/period, Stripe customer & subscription references. **Card data never touches Clairo systems** (Stripe Checkout hosted). |
| **Recipients**      | Stripe                                                                                                                                           |
| **Retention**       | Until account deletion; invoices retained by Stripe per its own legal obligations                                                                |

### 1.4 Sharing & referrals

|                     |                                                                                                                                                                           |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Purpose**         | User-initiated sharing of sanitized analyses; referral bonuses                                                                                                            |
| **Legal basis**     | Contract performance / legitimate interest **[LEGAL REVIEW REQUIRED]**                                                                                                    |
| **Data categories** | Share links (auto-expire after 30 days, revocable, serve only sanitized output — no document text, no user identity); referral relationships (user ids, completion state) |
| **Retention**       | Until link expiry/revocation or account deletion (FK cascade)                                                                                                             |

### 1.5 Analytics (consent-based)

|                     |                                                                                                                                                                        |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Purpose**         | Anonymous product usage statistics                                                                                                                                     |
| **Legal basis**     | Consent (Art. 6(1)(a)) — granular banner; PostHog is not even downloaded before opt-in                                                                                 |
| **Data categories** | 8 whitelisted events with metadata only (path, mime type, document type, counts). **No PII** (random anonymous id; `identify()` never called), **no document content** |
| **Recipients**      | PostHog (EU host)                                                                                                                                                      |
| **Retention**       | Per PostHog project settings **[LEGAL REVIEW REQUIRED — set and document]**                                                                                            |

### 1.6 Abuse prevention & security

|                     |                                                                                                                                                              |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Purpose**         | Rate limiting, quota enforcement, audit trail                                                                                                                |
| **Legal basis**     | Legitimate interest (Art. 6(1)(f))                                                                                                                           |
| **Data categories** | IP address (hashed into rate-limit/quota counters, Redis TTL ≤ 2 years), device id (client-generated), audit log (action + metadata, never document content) |
| **Retention**       | Redis keys expire by TTL; audit log rows are anonymised on account deletion (`user_id` set NULL)                                                             |

---

## 2. Data subject rights — implementation map

| Right                                | Implementation                                                                                                                                                                                   |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Access / portability (Art. 15/20)    | `GET /api/v1/account/export` — full JSON export (account, subscription, analyses, share links, referrals, audit log)                                                                             |
| Erasure (Art. 17)                    | `POST /api/v1/account/delete` — synchronous `gdpr_delete_user()`: hard-deletes the user row, cascading to subscriptions, analyses, share links, referrals; completes within the request (« 30 s) |
| Rectification (Art. 16)              | Account settings (language prefs); email via Clerk                                                                                                                                               |
| Consent withdrawal (Art. 7(3))       | Decline in the consent banner at any time; offline-cache clearing in account settings                                                                                                            |
| Objection / restriction (Art. 18/21) | Contact **[LEGAL REVIEW REQUIRED — process + address]**                                                                                                                                          |

## 3. Deletion cascade (technical record)

`gdpr_delete_user(p_user_id)` executes `DELETE FROM users` in one
transaction. Foreign keys with `ON DELETE CASCADE`: `subscriptions`,
`analyses` (→ `share_links` cascades from analyses), `referrals` (both
referrer and referred sides). `audit_log.user_id` is `SET NULL` (rows
kept, anonymised, for security compliance). A `gdpr.user_deleted` audit
row records the deletion event without personal data.
