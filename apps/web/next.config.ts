import type { NextConfig } from "next";

const productionApiOrigin = "https://kshr-ai--ambrosia-health-domain-api-api.modal.run";
const stagingApiOrigin = "https://kshr-ai-staging--ambrosia-health-domain-api-api.modal.run";
const productionHosts = [
  "ambrosia-ehr.vercel.app",
  "ambrosia-ehr-kshr.vercel.app",
  "ambrosia-ehr-git-main-kshr.vercel.app",
];

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  poweredByHeader: false,
  async rewrites() {
    const configuredOrigin = process.env.AMBROSIA_API_ORIGIN?.trim() || undefined;
    const apiOrigin = (configuredOrigin ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined))?.replace(/\/$/, "");
    if (apiOrigin) {
      return [
        {
          source: "/api/:path*",
          destination: `${apiOrigin}/api/:path*`,
        },
      ];
    }

    return {
      beforeFiles: productionHosts.map((host) => ({
        source: "/api/:path*",
        destination: `${productionApiOrigin}/api/:path*`,
        has: [{ type: "host" as const, value: host }],
      })),
      afterFiles: [],
      fallback: [
        {
          source: "/api/:path*",
          destination: `${stagingApiOrigin}/api/:path*`,
        },
      ],
    };
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
