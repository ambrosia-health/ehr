# Repository agent rules

## Performance and infrastructure

- Treat performance as a product requirement for every frontend, backend, data, and infrastructure change. Read `docs/performance.md` before changing runtime behavior.
- Preserve the global backend request/database instrumentation, request correlation, structured route logs, and `Server-Timing` headers. New backend routes must be observable without route-specific setup.
- Send frontend HTTP traffic through the shared API client and preserve route-transition, API, Core Web Vitals, Vercel Web Analytics, and Speed Insights instrumentation. New frontend routes must be observable without manual wiring.
- Benchmark affected local or hosted routes before and after material changes. Use production telemetry to identify the dominant bottleneck, make the smallest durable improvement, and verify the result after deployment.
- Maintain or tighten latency and query-count regression budgets when behavior changes. Do not merge a performance regression without documenting the measured tradeoff.
- Keep Neon, Modal, Vercel, secrets, environments, deployments, and monitoring centrally managed so a fresh checkout requires no manual infrastructure administration. Never commit secrets.
- Preserve scale-to-zero CPU infrastructure unless product requirements justify a different cost/latency tradeoff. Do not introduce GPU model hosting when the configured OpenAI model satisfies the requirement.
