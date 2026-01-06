import createNextIntlPlugin from 'next-intl/plugin'

const withNextIntl = createNextIntlPlugin('./i18n/request.ts')

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow connections to the backend API
  async rewrites() {
    return []
  },
}

export default withNextIntl(nextConfig)
