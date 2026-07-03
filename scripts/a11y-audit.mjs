/**
 * CLR-051 — axe-core audit over server-rendered screens.
 *
 * Fetches SSR HTML from the dev server and runs axe-core in jsdom.
 * jsdom does no layout, so the color-contrast rule is excluded here —
 * contrast is verified separately, mathematically, against the design
 * tokens (see the CLR-051 commit message for the pair-by-pair results).
 *
 * Usage: node scripts/a11y-audit.mjs [baseUrl]
 * Exits 1 if any critical or serious violation is found.
 */
import { JSDOM } from 'jsdom'
import axe from 'axe-core'

const BASE = process.argv[2] ?? 'http://localhost:3000'

// Public, server-renderable screens. Auth-gated screens (dashboard,
// account, upload, OCR review, results) can't be SSR'ed without a
// session — they are covered by the eslint jsx-a11y gate + code audit.
const SCREENS = [
  ['landing', '/'],
  ['pricing', '/pricing'],
  ['privacy', '/privacy'],
  ['terms', '/terms'],
  ['shared-unavailable', '/s/1b671a64-40d5-491e-99b0-da01ff1f3341'],
  ['not-found', '/definitely-not-a-page'],
  ['referral-redirect', '/ref/1b671a64-40d5-491e-99b0-da01ff1f3341'],
  ['sign-in', '/sign-in'],
]

// Rules that require real layout/rendering — meaningless in jsdom.
const SKIPPED_RULES = ['color-contrast']

let totalBlocking = 0

for (const [name, path] of SCREENS) {
  const res = await fetch(`${BASE}${path}`, { redirect: 'follow' })
  const html = await res.text()

  const dom = new JSDOM(html, { url: `${BASE}${path}` })
  const { window } = dom

  // axe needs a global window/document while it runs
  global.window = window
  global.document = window.document

  const results = await axe.run(window.document.documentElement, {
    rules: Object.fromEntries(SKIPPED_RULES.map((r) => [r, { enabled: false }])),
  })

  const blocking = results.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious'
  )
  const minor = results.violations.filter(
    (v) => v.impact !== 'critical' && v.impact !== 'serious'
  )

  console.log(
    `${name.padEnd(20)} status=${res.status}  critical/serious=${blocking.length}  other=${minor.length}`
  )
  for (const v of results.violations) {
    console.log(`  [${v.impact}] ${v.id}: ${v.help}`)
    for (const node of v.nodes.slice(0, 3)) {
      console.log(`      ${node.html.slice(0, 120)}`)
    }
  }
  totalBlocking += blocking.length

  delete global.window
  delete global.document
}

console.log(`\nTotal critical/serious violations: ${totalBlocking}`)
process.exit(totalBlocking > 0 ? 1 : 0)
