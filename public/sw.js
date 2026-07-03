/**
 * CLR-048 — Clairo service worker: offline access to cached analyses.
 *
 * Deliberately MINIMAL. It intercepts exactly one thing: GET requests to
 * /api/v1/analyses (any origin — the API may live on a subdomain).
 * Strategy: network-first. On success the response is trimmed to the 10
 * most recent analyses and cached; offline, the cached copy is served
 * with X-Clairo-Cache headers so the UI can show a "saved copy from
 * <date>" banner.
 *
 * NOT cached: static assets, pages, uploads, or any other API route —
 * uploads and new analyses require a connection by design, and app-shell
 * caching is left to the CDN/browser cache (avoids stale-bundle bugs).
 *
 * PRIVACY: only structured analysis summaries are ever in this cache
 * (the history endpoint returns metadata + AI summaries, never document
 * content). The user can wipe it from account settings (Offline section),
 * which deletes the whole cache bucket.
 */

const CACHE_NAME = 'clairo-analyses-v1'
const ANALYSES_PATH = '/api/v1/analyses'
const MAX_CACHED_ANALYSES = 10

self.addEventListener('install', (event) => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

// Page code (account settings) asks us to clear the offline cache.
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CLEAR_ANALYSES_CACHE') {
    event.waitUntil(caches.delete(CACHE_NAME))
  }
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'GET' || url.pathname !== ANALYSES_PATH) {
    return // fall through to the network untouched
  }
  event.respondWith(networkFirstAnalyses(event.request))
})

async function networkFirstAnalyses(request) {
  const cache = await caches.open(CACHE_NAME)
  try {
    const response = await fetch(request)
    if (response.ok) {
      await cacheTrimmedCopy(cache, request, response.clone())
    }
    return response
  } catch (_networkError) {
    const cached = await cache.match(request, { ignoreSearch: true })
    if (cached) return cached
    // No cached copy — a JSON error the UI treats like a fetch failure.
    return new Response(
      JSON.stringify({ detail: 'offline', items: [], total: 0 }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    )
  }
}

async function cacheTrimmedCopy(cache, request, response) {
  try {
    const data = await response.json()
    const items = Array.isArray(data.items)
      ? data.items.slice(0, MAX_CACHED_ANALYSES)
      : []
    const body = JSON.stringify({ items, total: items.length })
    const cachedResponse = new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'X-Clairo-Cache': 'hit',
        'X-Clairo-Cached-At': new Date().toISOString(),
      },
    })
    await cache.put(request, cachedResponse)
  } catch (_parseError) {
    // Unparseable body — skip caching rather than poison the cache.
  }
}
