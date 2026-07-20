# Ambrosia web

Next.js 16 frontend for the dermatologist operating workspace. The canonical product is intentionally small: `/` is Today, `/patients` is the patient worklist, `/patients/[patientId]` is the focused clinical decision brief, and `/practice` is the quiet proof that administrative work is moving. There is no clinician-facing browser login, persona switcher, patient portal, or compatibility route. `/internal/learning` is a deliberately separate presenter-gated synthetic evaluation console and never appears in clinician navigation.

All product views load a single authenticated, tenant-scoped workspace from `/api/demo/bootstrap`. Approvals, note edits, and AI commands use domain mutation endpoints and persist to the configured database; frontend code contains no patient, queue, metric, recommendation, or workflow fixtures. Browser HTTP traffic uses `src/lib/api/client.ts` so request timing, correlation IDs, and `Server-Timing` stay observable.

## Local development

The repository-root `make dev` command is the preferred zero-credential path. For web-only work against an already running API:

```bash
npm install
cp .env.example .env.local
npm run dev
```

`AMBROSIA_API_ORIGIN` is required everywhere. Root `make` targets export the local FastAPI origin; the managed reconciliation script assigns Modal main to Vercel Production and Modal staging to Vercel Preview. There is no host-based or environment-specific routing fallback in application code.

## Quality gates

```bash
npm run lint
npm run typecheck
npm test
AMBROSIA_API_ORIGIN=http://127.0.0.1:8000 npm run build
npm run e2e
```

Playwright verifies direct product entry, the four canonical clinician routes, database-backed workspace content, removal of legacy routes, and the same-origin API/session/observability contract. Local E2E expects FastAPI at `AMBROSIA_API_ORIGIN`; `make e2e` is the normal integrated path.

`npm run e2e:hosted` requires an HTTPS `NEXT_PUBLIC_APP_URL` and never starts a local substitute server. Infrastructure maintainers normally invoke it through [`../../scripts/provision-managed-infra.sh`](../../scripts/provision-managed-infra.sh).

## Deployment

The managed Vercel project is `ambrosia-ehr` (`prj_ad1AsXV5muySOAyBsxMgcKAj1SVa`), its Root Directory is `apps/web`, and its canonical synthetic-demo site is [ambrosia-ehr.vercel.app](https://ambrosia-ehr.vercel.app). Native Git integration creates branch/PR previews and deploys `main`; no `VERCEL_TOKEN` or per-contributor environment setup is required.

Vercel carries one non-secret, server-only `AMBROSIA_API_ORIGIN` binding per environment. [`../../scripts/provision-managed-infra.sh`](../../scripts/provision-managed-infra.sh) reconciles those bindings alongside Neon, Modal, GitHub secrets, and hosted verification.

Vercel’s `Production` environment name does not make this application suitable for clinical production. The site contains synthetic people and simulated networks only; real PHI remains prohibited until every documented production gate is closed.
