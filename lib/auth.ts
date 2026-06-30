/**
 * Auth helpers — server-side only.
 *
 * Usage in Server Components / Route Handlers:
 *   import { getBackendAuthHeaders } from '@/lib/auth'
 *   const headers = await getBackendAuthHeaders()
 *   fetch(`${API_URL}/api/v1/analyse`, { headers })
 */
import { auth } from '@clerk/nextjs/server'

/**
 * Returns an Authorization header containing the Clerk JWT,
 * ready to attach to requests going to the FastAPI backend.
 *
 * The backend (CLR-031) will verify this token via Clerk's JWKS endpoint.
 */
export async function getBackendAuthHeaders(): Promise<Record<string, string>> {
  const { getToken } = auth()
  const token = await getToken()

  if (!token) {
    throw new Error('Not authenticated')
  }

  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
}

/**
 * Returns the current user's Clerk user ID (sub claim).
 * Throws if not authenticated.
 */
export function requireUserId(): string {
  const { userId } = auth()
  if (!userId) throw new Error('Not authenticated')
  return userId
}
