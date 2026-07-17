# Performance observability and budgets

Ambrosia instruments both runtime boundaries without requiring contributors or agents to configure credentials or environment variables.

## Frontend

- Vercel Web Analytics records route usage, while Speed Insights records route-attributed LCP, INP, CLS, FCP, and TTFB from real browsers.
- Next.js client instrumentation marks every initial load and router transition with `ambrosia.route-start`, `ambrosia.route-ready`, and `ambrosia.route-transition` User Timing entries.
- The API client records every same-origin request as `ambrosia.api`, including normalized route, method, outcome, duration, correlation ID, and the backend `Server-Timing` value. Dynamic identifiers are replaced with `:id` before aggregation.
- Slow route transitions, poor Core Web Vitals, failed API requests, and API requests over one second emit structured browser warnings. These warnings contain no request bodies, patient identifiers, or response data.

Use the Vercel project dashboards at `/analytics`, `/speed-insights`, and `/logs`. Future agents should rank route-level p75 Core Web Vitals before changing rendering, caching, images, or client boundaries.

## Backend

Every FastAPI request emits one JSON `http_request` event to Modal logs with the route template, status, total duration, database duration/share, SQL statement count, slow-query count, response size, deployment environment, region, and request ID. Statements over 250 ms emit a separate `slow_database_query` event containing only the SQL operation—not SQL text, parameters, raw paths, or identifiers.

Every API response exposes:

```text
X-Request-ID: <correlation id>
Server-Timing: app;dur=<milliseconds>, db;dur=<milliseconds>;desc="<count> queries"
```

Capture a bounded Modal log sample, then summarize it with the repository command:

```bash
.venv/bin/modal app logs ambrosia-health-domain-api --env main > /tmp/ambrosia-modal.log
.venv/bin/ambrosia-perf-report /tmp/ambrosia-modal.log
```

Stop the log capture after the representative journey completes. The report ranks route p95 and shows average database time and query count, separating network/database pressure from application work.

## Regression gates

- `backend/tests/test_observability.py` requires correlation and timing headers, structured privacy-safe route logs, and a bootstrap ceiling of 150 SQL statements and one second against the local test database.
- `apps/web/e2e/api-contract.spec.ts` requires timing headers through the real Next.js rewrite and caps bootstrap server duration at five seconds in local and hosted E2E.
- Web lint, typecheck, component tests, production build, browser product/API contracts, Modal model/database attestation, and the performance contract run on every relevant `main` deployment.

## Optimization loop

1. Run the canonical browser product/API contracts to generate representative route and API traffic.
2. Rank Vercel route Core Web Vitals and Modal request p95; do not optimize averages first.
3. Use database share and query count to distinguish query/region problems from Python serialization or external API latency.
4. Make one bounded change, rerun the regression gates, deploy, then compare the same p75/p95 window.
5. Keep public contracts and human safety gates intact. Performance work must not add stale clinical state, weaken tenant filters, or cache authenticated responses across users.

Modal API and workflow containers are pinned to `us-east`, colocated with the Neon `aws-us-east-1` project. They remain scale-to-zero with no warm-container or GPU requirement.
