import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  poweredByHeader: false,
  async rewrites() {
    const configuredOrigin = process.env.AMBROSIA_API_ORIGIN?.trim() || undefined;
    const managedVercelOrigin = process.env.VERCEL_ENV === "production"
      ? "https://kshr-ai--ambrosia-health-domain-api-api.modal.run"
      : process.env.VERCEL_ENV === "preview"
        ? "https://kshr-ai-staging--ambrosia-health-domain-api-api.modal.run"
        : undefined;
    const apiOrigin = (configuredOrigin ?? managedVercelOrigin ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined))?.replace(/\/$/, "");
    if (!apiOrigin) {
      throw new Error("AMBROSIA_API_ORIGIN is required for production builds and deployments.");
    }
    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          { key: "Cache-Control", value: "private, no-store, max-age=0" },
          { key: "Vary", value: "Cookie" },
        ],
      },
      {
        source: "/:path*",
        headers: [
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(self), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
