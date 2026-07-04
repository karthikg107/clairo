import createNextIntlPlugin from 'next-intl/plugin'

const withNextIntl = createNextIntlPlugin('./lib/i18n/request.ts')

// CLR-054 — the API may live on its own origin (api.clairo.app in prod,
// the mock server in E2E). connect-src 'self' alone blocked every
// cross-origin API call; the API origin, Clerk, and PostHog must be
// allowed explicitly.
const apiOrigin = process.env.NEXT_PUBLIC_API_URL || ''
const posthogOrigin = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://eu.i.posthog.com'
const connectSrc = ["'self'", apiOrigin, posthogOrigin, 'https://*.clerk.accounts.dev']
  .filter(Boolean)
  .join(' ')

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(self), microphone=(), geolocation=()',
          },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              // Clerk loads clerk.browser.js from the instance domain
              "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://*.clerk.accounts.dev",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob: https://img.clerk.com",
              `connect-src ${connectSrc}`,
              "frame-ancestors 'none'",
            ].join('; '),
          },
        ],
      },
    ]
  },

  images: {
    formats: ['image/webp', 'image/avif'],
  },

  experimental: {
    // lucide-react is also in Next's built-in list; kept explicit so the
    // per-icon import transform (CLR-050 bundle splitting) is documented.
    optimizePackageImports: ['clsx', 'tailwind-merge', 'lucide-react'],
  },
}

export default withNextIntl(nextConfig)
