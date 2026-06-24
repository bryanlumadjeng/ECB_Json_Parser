/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // In local development, proxy /api/* to the local FastAPI backend.
    // On Vercel, /api/* is served by the Python serverless functions directly.
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    if (process.env.NODE_ENV === "development") {
      return [
        {
          source: "/api/:path*",
          destination: `${backendUrl}/api/:path*`,
        },
      ];
    }
    return [];
  },
};

module.exports = nextConfig;
