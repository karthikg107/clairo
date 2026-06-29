import { useTranslations } from 'next-intl'

export default function HomePage() {
  const t = useTranslations('home')
  return (
    <main className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="text-center max-w-md">
        <h1 className="text-3xl font-bold text-brand-500 mb-2">
          {t('headline')}
        </h1>
        <p className="text-dark-text/70">{t('subheadline')}</p>
      </div>
    </main>
  )
}
