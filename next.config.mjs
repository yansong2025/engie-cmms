/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  // In production Vercel serves api/analyze.py itself. Locally, forward the
  // call to the uvicorn process described in the README.
  async rewrites() {
    if (process.env.NODE_ENV !== 'development') return []
    return [{ source: '/api/:path*', destination: 'http://127.0.0.1:8000/api/:path*' }]
  },
}

export default nextConfig
