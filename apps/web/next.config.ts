import type { NextConfig } from "next";

const configuredApiOrigin = process.env.AMBROSIA_API_ORIGIN?.trim();
if (!configuredApiOrigin) {
  throw new Error("AMBROSIA_API_ORIGIN is required in local, preview, and production environments.");
}

const apiOriginUrl = new URL(configuredApiOrigin);
if (!["http:", "https:"].includes(apiOriginUrl.protocol)) {
  throw new Error("AMBROSIA_API_ORIGIN must use http or https.");
}
const apiOrigin = configuredApiOrigin.replace(/\/$/, "");

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
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
