import { NextIntlClientProvider } from 'next-intl'
import { getMessages } from 'next-intl/server'
import { Inter } from 'next/font/google'
import { notFound } from 'next/navigation'
import { locales, type Locale } from '@/i18n'

const inter = Inter({ subsets: ['latin'] })

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }))
}

export default async function LocaleLayout({
  children,
  params: { locale }
}: {
  children: React.ReactNode
  params: { locale: string }
}) {
  // Validate locale
  if (!locales.includes(locale as Locale)) {
    notFound()
  }

  // Get messages for the locale
  const messages = await getMessages()

  return (
    <html lang={locale} className="dark">
      <body className={`${inter.className} bg-bg-primary text-text-primary min-h-screen`}>
        <NextIntlClientProvider messages={messages}>
          <div className="flex flex-col min-h-screen">
            {/* Header */}
            <header className="border-b border-border bg-bg-secondary/50 backdrop-blur-sm sticky top-0 z-50">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                  {/* Logo */}
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-gradient-to-br from-accent-blue to-accent-purple rounded-lg flex items-center justify-center">
                      <span className="text-white font-bold text-sm">SG</span>
                    </div>
                    <span className="text-xl font-bold text-gradient">SnapPlan</span>
                  </div>

                  {/* Right side */}
                  <div className="flex items-center gap-4">
                    {/* Language Toggle */}
                    <div className="flex items-center gap-1 bg-bg-card rounded-lg p-1">
                      <a
                        href="/de"
                        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                          locale === 'de'
                            ? 'bg-accent-blue text-white'
                            : 'text-text-secondary hover:text-text-primary'
                        }`}
                      >
                        DE
                      </a>
                      <a
                        href="/en"
                        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                          locale === 'en'
                            ? 'bg-accent-blue text-white'
                            : 'text-text-secondary hover:text-text-primary'
                        }`}
                      >
                        EN
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </header>

            {/* Main Content */}
            <main className="flex-1">
              {children}
            </main>

            {/* Footer */}
            <footer className="border-t border-border bg-bg-secondary/30 py-6">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-text-muted">
                  <p>SnapPlan v0.1.0 Alpha</p>
                  <p>API: {process.env.NEXT_PUBLIC_SNAPGRID_API_URL || 'http://localhost:8000'}</p>
                </div>
              </div>
            </footer>
          </div>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
