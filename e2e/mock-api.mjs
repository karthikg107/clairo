/**
 * CLR-054 — tiny mock backend for E2E runs.
 *
 * Serves the endpoints the NEXT SERVER calls server-side (which
 * page.route() cannot intercept — it only sees browser traffic):
 * currently GET /api/v1/shared/:id for the /s/[shareId] page.
 * Browser-side API calls are mocked per-test with page.route().
 *
 * All payloads are synthetic — no document content.
 */
import http from 'node:http'

const PORT = 4010
export const LIVE_SHARE_ID = '1b671a64-40d5-491e-99b0-da01ff1f3341'

const SHARED_RESPONSE = {
  document_type: 'rental',
  summary: 'SYNTHETIC-TEST-SUMMARY for a shared analysis page.',
  clauses: [
    {
      id: 'c1',
      title: 'Deposit',
      explanation: 'SYNTHETIC-TEST-EXPLANATION for the shared page.',
      frequency_pct: 60,
      is_protective: false,
      flag_level: 'review',
    },
  ],
  protective_clause_count: 0,
  review_clause_count: 1,
  doc_language: 'de',
  output_language: 'en',
  analysed_at: '2026-07-01T00:00:00+00:00',
  expires_at: '2026-08-01T00:00:00+00:00',
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`)

  if (req.method === 'GET' && url.pathname === `/api/v1/shared/${LIVE_SHARE_ID}`) {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(SHARED_RESPONSE))
    return
  }
  if (req.method === 'GET' && url.pathname.startsWith('/api/v1/shared/')) {
    res.writeHead(404, { 'Content-Type': 'application/json' })
    res.end(
      JSON.stringify({
        detail: { error: 'share_not_found', message: 'This link is no longer available.' },
      })
    )
    return
  }
  if (url.pathname === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end('{"ok":true}')
    return
  }

  // Anything else: a browser-side call that a test forgot to mock, or a
  // server-side call we don't support — 503 makes the gap loud.
  res.writeHead(503, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify({ detail: 'mock-api: unmocked endpoint ' + url.pathname }))
})

server.listen(PORT, () => {
  console.log(`mock-api listening on :${PORT}`)
})
