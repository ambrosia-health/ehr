# Ambrosia web

Next.js 16 frontend for the Ambrosia dermatology operating-system demo. The browser talks only to same-origin `/api/*`; Next.js rewrites those requests to the FastAPI domain service using the server-only `AMBROSIA_API_ORIGIN`.

## Local development

The repository-root `make dev` command is the preferred zero-credential path and creates all synthetic-safe local configuration automatically. For web-only work against an already running API:

```bash
npm install
cp .env.example .env.local
npm run dev
```

`AMBROSIA_API_ORIGIN` defaults to `http://127.0.0.1:8000` only in development. It is mandatory for production builds and deployments.

## Quality gates

```bash
npm run lint
npm run typecheck
npm test
AMBROSIA_API_ORIGIN=http://127.0.0.1:8000 npm run build
```

The live browser journey requires the real API and a protected presenter credential:

```bash
E2E_LIVE_API=1 \
PRESENTER_ACCESS_CODE=... \
AMBROSIA_API_ORIGIN=http://127.0.0.1:8000 \
npm run e2e
```

Local E2E skips when those credentials are absent; CI fails explicitly so the critical path cannot disappear silently.

`npm run e2e:hosted` uses `playwright.hosted.config.ts`, requires an HTTPS `NEXT_PUBLIC_APP_URL`, and never starts a local substitute server. Infrastructure maintainers normally invoke it through [`../../scripts/provision-managed-infra.sh`](../../scripts/provision-managed-infra.sh), which keeps the rotated presenter credential in memory and fails the reconciliation if the deployed journey fails.

## Deployment

The managed Vercel project is `ambrosia-ehr` (`prj_ad1AsXV5muySOAyBsxMgcKAj1SVa`), its Root Directory is `apps/web`, and its canonical synthetic-demo site is [ambrosia-ehr.vercel.app](https://ambrosia-ehr.vercel.app). Native Git integration with `ambrosia-health/ehr` creates branch/PR previews and deploys `main`; no `VERCEL_TOKEN` or manual per-contributor environment setup is required. `.github/workflows/vercel-preview.yml` verifies pull requests and smoke-tests successful non-production deployment events rather than creating a second CLI deployment.

Managed Preview `AMBROSIA_API_ORIGIN` targets the synthetic Modal staging API; Production targets the synthetic Modal main API. [`../../scripts/provision-managed-infra.sh`](../../scripts/provision-managed-infra.sh) is the authorized reconciliation path for these bindings and the corresponding platform secrets. `vercel.json` intentionally contains only schema and framework selection; build and output behavior remain Next.js defaults.

Never set `NEXT_PUBLIC_DEMO_TEST_MODE=true` in production. Presenter capability comes only from the signed HTTP-only session returned by the domain API.

Vercel's `Production` environment name does not make this application suitable for clinical production. The site contains synthetic people and simulated networks only; real PHI remains prohibited until every documented production gate is closed.
