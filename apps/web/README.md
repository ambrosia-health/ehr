# Ambrosia web

Next.js 16 frontend for the dermatologist operating workspace. `/` is the canonical Today view; Patients, Schedule, Inbox, Results, Revenue, Operations, and Sarah Mitchell’s care agent share one clinician shell. There is no browser login, persona switcher, patient portal, presenter console, or compatibility route.

The product views currently use explicit synthetic fixtures in `src/components/platform`. Backend domain workflows remain available through the same-origin `/api/*` rewrite. New browser HTTP traffic must use `src/lib/api/client.ts` so request timing, correlation IDs, and `Server-Timing` stay observable.

## Local development

The repository-root `make dev` command is the preferred zero-credential path. For web-only work against an already running API:

```bash
npm install
cp .env.example .env.local
npm run dev
```

`AMBROSIA_API_ORIGIN` defaults to `http://127.0.0.1:8000` in development. Managed deployments need no routing variable: canonical and main-branch hosts route to Modal main, while previews and unknown hosts route to Modal staging.

## Quality gates

```bash
npm run lint
npm run typecheck
npm test
AMBROSIA_API_ORIGIN=http://127.0.0.1:8000 npm run build
npm run e2e
```

Playwright verifies direct product entry, every canonical clinician route, removal of legacy routes, and the same-origin API/session/observability contract. Local E2E expects FastAPI at `AMBROSIA_API_ORIGIN`; `make e2e` is the normal integrated path.

`npm run e2e:hosted` requires an HTTPS `NEXT_PUBLIC_APP_URL` and never starts a local substitute server. Infrastructure maintainers normally invoke it through [`../../scripts/provision-managed-infra.sh`](../../scripts/provision-managed-infra.sh).

## Deployment

The managed Vercel project is `ambrosia-ehr` (`prj_ad1AsXV5muySOAyBsxMgcKAj1SVa`), its Root Directory is `apps/web`, and its canonical synthetic-demo site is [ambrosia-ehr.vercel.app](https://ambrosia-ehr.vercel.app). Native Git integration creates branch/PR previews and deploys `main`; no `VERCEL_TOKEN` or per-contributor environment setup is required.

Vercel carries no application secrets. Environment-safe Modal bindings live in `next.config.ts`; [`../../scripts/provision-managed-infra.sh`](../../scripts/provision-managed-infra.sh) reconciles Neon, Modal, GitHub secrets, and hosted verification.

Vercel’s `Production` environment name does not make this application suitable for clinical production. The site contains synthetic people and simulated networks only; real PHI remains prohibited until every documented production gate is closed.
