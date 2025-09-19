/** @type {import('next').NextConfig} */
const nextConfig = {
  // Desktop app configuration
  output: 'export',
  trailingSlash: true,
  distDir: 'build',

  // Asset optimization for Electron
  images: {
    unoptimized: true,
  },
  
  // Build configuration
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  
  // Environment variables for desktop app
  env: {
    NEXT_PUBLIC_API_URL: process.env.NODE_ENV === 'development' 
      ? 'http://localhost:8000' 
      : 'http://localhost:8000', // Always local in desktop app
    NEXT_PUBLIC_IS_DESKTOP: 'true',
  },
}

export default nextConfig
