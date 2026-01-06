/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow connections to the backend API
  async rewrites() {
    return []
  },
}

export default nextConfig
