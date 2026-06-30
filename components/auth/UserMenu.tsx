'use client'

import { UserButton, useUser } from '@clerk/nextjs'
import { useTranslations } from 'next-intl'

/**
 * Compact user menu — drops into any header/nav.
 * Shows the Clerk UserButton (avatar + dropdown with sign-out, profile link).
 */
export function UserMenu() {
  const { isLoaded, isSignedIn } = useUser()
  const t = useTranslations('auth')

  if (!isLoaded || !isSignedIn) return null

  return (
    <div className="flex items-center gap-2">
      <UserButton
        afterSignOutUrl="/sign-in"
        appearance={{
          elements: {
            avatarBox: 'w-8 h-8',
            userButtonPopoverCard:
              'shadow-lg border border-neutral-200 rounded-2xl',
            userButtonPopoverActionButton:
              'text-sm text-neutral-700 hover:bg-neutral-50',
            userButtonPopoverActionButtonText: 'text-sm',
            userButtonPopoverFooter: 'hidden',
          },
          variables: {
            colorPrimary: '#1B4F8A',
            borderRadius: '0.75rem',
            fontFamily: 'var(--font-inter)',
          },
        }}
      />
    </div>
  )
}
