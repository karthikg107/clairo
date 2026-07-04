# CLR-052 — Cross-Browser & Cross-Device Testing Matrix

> **HUMAN ACTION REQUIRED.** Automated coverage exists (Playwright
> mobile-Chromium E2E, axe audit, 375px-first design), but this ticket
> needs hands on real devices — rendering, camera, PWA install, and RTL
> behaviour differ physically per device/OS. Do not close CLR-052 until
> every P1 row below is signed off.

## Devices — priority order

| P   | Device                              | OS / Browser                  | Why                                                                               |
| --- | ----------------------------------- | ----------------------------- | --------------------------------------------------------------------------------- |
| P1  | iPhone SE / 12 mini                 | iOS Safari (latest)           | Smallest iOS viewport; Safari is the #1 divergence risk (PWA, camera, file input) |
| P1  | iPhone 14/15                        | iOS Safari + iOS Chrome       | Majority iOS traffic                                                              |
| P1  | Samsung Galaxy A-series (mid-range) | Android Chrome                | Target market's most common device class (IN/AE/DE)                               |
| P1  | Xiaomi/Redmi (budget)               | Android Chrome + MIUI browser | Big in IN market; aggressive OS-level battery/permission quirks                   |
| P2  | Samsung Galaxy S-series             | Samsung Internet              | Samsung Internet ≠ Chrome (PWA install, file pickers)                             |
| P2  | iPad                                | iPadOS Safari                 | Tablet layout (sm: breakpoints)                                                   |
| P2  | Windows laptop                      | Chrome, Edge, Firefox         | Desktop fallback experience                                                       |
| P3  | macOS                               | Safari                        | Desktop Safari quirks                                                             |

## What to test on each device

### A. Core journey (every P1 device)

1. Landing page renders; trust strip visible without scrolling at 375px;
   animated demo loops; language banner rotates.
2. Upload flow: photograph a SYNTHETIC test contract with the camera →
   OCR review renders, words tappable/editable → language selection →
   analysis renders. **Camera behaviour is per-device — this cannot be
   automated.**
3. Gallery upload and PDF upload variants.
4. Share: WhatsApp button opens WhatsApp with prefilled message
   (device must have WhatsApp installed); copy-link works; native share
   sheet opens.
5. Shared link opened from WhatsApp renders the shared page with
   preview card (OG tags).

### B. PWA & offline (P1 mobile devices)

1. Visit 3 times → install prompt appears; install; app opens standalone
   with correct icon/theme colour.
2. Load dashboard signed-in → airplane mode → reopen: cached analyses
   with the date banner; upload surface disabled with the offline
   message → reconnect: banner clears, data refreshes.

### C. Localisation & RTL (at least one iOS + one Android)

1. Switch device language to Arabic and Urdu → whole UI mirrors (dir=rtl),
   chevrons flip, no clipped text.
2. Hindi/Devanagari and Urdu/Nastaliq scripts render legibly at small
   sizes (trust strip 11px, clause labels).
3. German (long compound words) doesn't overflow buttons at 375px.

### D. Payments (one iOS Safari + one Android Chrome)

1. Upgrade → Stripe Checkout opens and completes with a test card →
   returns to dashboard with the success banner.
2. Cancel → returns to /pricing.

### E. Accessibility spot checks (one device per OS)

1. VoiceOver (iOS) / TalkBack (Android) through the upload flow — all
   controls announced meaningfully.
2. Increase OS font size to 200% — no lost content.
3. Reduce Motion on → landing animations static.

## Known risk areas to watch

- iOS Safari: `beforeinstallprompt` does NOT exist — the install prompt
  will never show; verify Add-to-Home-Screen manually works instead.
- iOS Safari file input + HEIC uploads (backend accepts HEIC — verify
  end-to-end from an iPhone camera roll).
- Samsung Internet dark mode force-inverts colours — check disclaimer
  contrast.
- MIUI/Redmi aggressive background killing — verify camera permission
  and the SW survive.

## Sign-off

Record results per device in this table (copy to the tracking sheet):
`device | os/browser | A ✅/❌ | B | C | D | E | notes | tester | date`
