# Development, preview, and deployment

This runbook preserves the three-platform boundary: Vercel hosts Next.js, Modal hosts FastAPI/AI/workers, and Neon stores durable state. The managed deployment below is live and reproducible, but it is **synthetic demo infrastructure only**. A Vercel `Production` label, reachable Modal function, or Neon production branch does not authorize real PHI, clinical care, live networks, or patient-facing AI.

## Environment matrix

| Environment | Web | API/workers | Database | Data/network policy |
|---|---|---|---|---|
| Local | Next.js dev on `:3000` | same FastAPI app under Uvicorn on `:8000` | SQLite zero-credential default; optional Docker Postgres 16 | canonical synthetic seed; deterministic provider adapters; local AI fallback |
| Preview | native Vercel branch/PR Preview | managed Modal `staging` API | managed synthetic Neon `staging`; `preview` branch reserved for isolated migration/verification work | deterministic networks; OpenAI GPT-5.6 Luna with low reasoning and deterministic fallback |
| Staging | Vercel preview surface | managed Modal `staging` | isolated synthetic Neon `staging` branch | production-like demo configuration; no live provider credentials/data |
| Production | Vercel Production alias | managed Modal `main` | isolated synthetic Neon `main` branch | publicly hosted synthetic demo; every real-world P0 gate remains open until separately evidenced |

Never point a preview at the hosted-production Neon branch or any live provider credential. Keep synthetic branches, session keys, and Modal Secrets environment-bound; real-data use requires the stronger account/project/database/role isolation selected by the production threat model. `NEXT_PUBLIC_*` values are visible to anyone; only the public app URL belongs there.

## Managed resource registry

Identifiers and URLs below are operational metadata, not credentials. Connection strings, session keys, presenter codes, OpenAI keys, and CLI tokens remain only in platform secret stores.

| Platform | Managed resource | Binding |
|---|---|---|
| Vercel | project `ambrosia-ehr`, ID `prj_ad1AsXV5muySOAyBsxMgcKAj1SVa` | repository `ambrosia-health/ehr`; Root Directory `apps/web`; production branch `main`; canonical site [ambrosia-ehr.vercel.app](https://ambrosia-ehr.vercel.app); native Git previews enabled |
| Neon | project `ambrosia-ehr`, ID `round-cloud-23718842`; database `ambrosia` | `main` / `br-still-wildflower-aunolqvx` (hosted production demo), `staging` / `br-rough-feather-auv415ro`, `preview` / `br-lingering-queen-au7d3n4t` |
| Modal main | environment `main`, app `ambrosia-health-domain-api` | API `https://kshr-ai--ambrosia-health-domain-api-api.modal.run`; dashboard [deployment](https://modal.com/apps/kshr-ai/main/deployed/ambrosia-health-domain-api) |
| Modal staging | environment `staging`, app `ambrosia-health-domain-api` | API `https://kshr-ai-staging--ambrosia-health-domain-api-api.modal.run` |

The domain APIs call OpenAI directly with `OPENAI_API_KEY` injected from environment-specific Modal Secrets. There is no public or internal model endpoint.

## Local workflow

```bash
make dev
```

The command creates `.env` from the synthetic-safe template when absent, installs `backend[dev]` into `.venv`, installs the web lockfile, creates a disposable local SQLite database, migrates, idempotently seeds, then runs both processes. No Neon, Modal, Vercel, GitHub, Docker, or cloud credential is required. Validate from another terminal:

```bash
make demo-health
make test
```

Run the same application against Postgres 16 when Docker is available:

```bash
make dev-postgres
make test-postgres
```

SQLite makes the demo runnable without credentials or hosted dependencies; it is not the hosted architecture. CI also migrates/seeds/tests a localhost Postgres 16 service, and deployed environments use Neon Postgres. Pytest defaults to an isolated temporary SQLite database; it may honor an explicit database URL only for `APP_ENV=test`, `ALLOW_TEST_DATABASE_RESET=true`, and either a local host or an exact `EPHEMERAL_TEST_DATABASE_HOST`. The remote-host option is reserved for an expiring, disposable Neon branch created and deleted by the infrastructure operator; it must never name staging or production.

The CI matrix independently runs backend SQLite tests, a Postgres 16 migration/seed/invariant suite, web lint/type/test/build, and an integrated Playwright journey. The browser journey keeps `NEXT_PUBLIC_DEMO_TEST_MODE=false` and exercises real signed login/persona-switch cookies. `X-Demo-Persona` is reserved for isolated API tests and is accepted only when backend `APP_ENV=test` is explicit; it must never authenticate the integrated browser journey.

For a local browser run, start from the canonical state with `make reset`, keep `make dev` running, and invoke `make e2e` in a second terminal. The Make target reads the presenter code from `.env`, opts into the live-stack spec, and leaves the persona header disabled. The CI job additionally parses Playwright's JSON report and fails an all-skipped run.

Reset only the configured synthetic scenario:

```bash
make reset
```

`reset` must refuse when the backend environment is not explicitly synthetic. `docker compose down -v` is intentionally not a product reset: it destroys the optional entire local Postgres volume and bypasses scenario safeguards.

## Configuration contract

### Vercel server environment

| Variable | Scope | Purpose |
|---|---|---|
| `AMBROSIA_API_ORIGIN` | Preview/Production server only | Override for the corresponding Modal ASGI origin used by the same-origin `/api` rewrite. The registered production/preview origins are also selected from `VERCEL_ENV`, so a Git deployment cannot lose API routing solely because Vercel omits build-time env injection. |
| `NEXT_PUBLIC_APP_URL` | public | Canonical web origin for links; contains no secret. |
| `NEXT_PUBLIC_DEMO_TEST_MODE` | public | Keep `false` for local, preview, production and integrated E2E. It may be `true` only in an isolated frontend/API harness whose backend is explicitly `APP_ENV=test`; that harness alone may send `X-Demo-Persona`. |
| `PRESENTER_ACCESS_CODE` | protected server-only | Synthetic hosted-E2E credential synchronized with Modal and GitHub; never exposed through `NEXT_PUBLIC_*` or application responses. |
| `BLOB_READ_WRITE_TOKEN` | server only, if uploads enabled | Private synthetic upload adapter. Do not expose to the browser. |

Frontend requests remain `/api/...`. Next.js performs a same-origin rewrite to Modal, preserving the browser's session request. Modal authenticates and authorizes it, assigns or returns `X-Request-ID`, and emits private/no-store headers; Next adds matching no-store and `Vary: Cookie` headers. A lightweight Next.js request Proxy performs only an optimistic product-route cookie check, keeping presentation routes static and prefetchable; Modal remains the authorization boundary for every read and mutation. This demo does not implement a custom route-handler proxy or a header/body allowlist. Explicit forwarding rules and body/time limits are production gates if the API rewrite is replaced by an application proxy.

### Modal runtime secret

Create a Modal Secret named `ambrosia-runtime` in each Modal environment containing at minimum `DATABASE_URL`, `AUTH_SESSION_SECRET`, `DEMO_PRESENTER_SECRET` (synthetic demo environments only, including the current hosted Production alias), `APP_ENV`, `EXECUTION_PLATFORM=modal`, `DEMO_MODE`, `SESSION_COOKIE_SECURE`, `AUTO_CREATE_SCHEMA=false`, `AUTO_SEED=false`, `CORS_ORIGINS`, and provider adapter selections. Create the narrower `ambrosia-openai` secret containing only `OPENAI_API_KEY`; attach it only to the domain API function. Hosted Neon URLs require TLS. Keep a separate direct/migration URL in protected CI rather than application containers where feasible.

The demo Modal wrapper must declare the intended secret name and ASGI app; merely setting local shell variables does not inject them into a deployed container.

The current `backend.modal_app` contract is deliberately small:

- `modal.App("ambrosia-health-domain-api")` builds a Python 3.12 image from the locked backend project and mounts the `app` package;
- `api` exposes the FastAPI application through `@modal.asgi_app()` and is the only web endpoint;
- the domain API calls OpenAI `gpt-5.6-luna` through the Responses API with `reasoning.effort=low`, `store=false`, and no GPU or local model weights;
- the AI application layer hashes the versioned prompt, parses output into the capability schema, applies semantic constraints (including allowed-code, urgency, grounding, and uncertainty-routing checks), and labels a run live only when exact provider/model/reasoning attestation is present;
- timeout, provider failure, malformed JSON, schema failure, semantic failure, missing provenance, or model mismatch selects the deterministic `ambrosia-fixture-2026.1` fallback. Live and fallback outputs remain proposals subject to the same human gate;
- `durable_workflow_poller` wakes every five minutes, reads due scheduled reminders and overdue tasks from Postgres, invokes the messaging simulator, and escalates task priority. Postgres remains authoritative. This is not yet a general lease/retry/dead-letter worker engine; that is a pilot gate.

`backend/uv.lock` is the Modal SDK/CLI authority and currently resolves Modal 1.5.2. CI installs it with `uv sync --locked`; update `pyproject.toml` and the lockfile together, then revalidate decorators and `modal deploy -m backend.modal_app` before merging an SDK upgrade.

### GitHub environments and secrets

| Secret/variable | Workflow |
|---|---|
| `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | Modal CLI deployment identity |
| `NEON_DATABASE_URL_DIRECT` | protected migration job; environment-specific |
| `MODAL_API_HEALTH_URL` | post-deploy authenticated/non-sensitive health endpoint URL |
| `OPENAI_API_KEY` | synchronized into `ambrosia-openai`; exact provider/model/reasoning contract attestation |
| `PRESENTER_ACCESS_CODE` | protected hosted demo/E2E access retained only in platform secret stores and provisioner process memory |

GitHub `staging` and `production` environments are provisioned and environment-specific; the latter carries the secrets for Modal `main` and the hosted Vercel production alias. Enforce required reviewers before treating it as a controlled release boundary. Restrict deployment credentials to service identities, rotate them, and never echo credential-bearing URLs or environment files. Native Vercel Git deployment does **not** require `VERCEL_TOKEN` in GitHub.

## Managed reconciliation and attestation

Authorized platform operators use one desired-state reconciliation entrypoint:

```bash
./scripts/provision-managed-infra.sh
```

The script requires already authenticated `gh`, `neonctl`, Modal, and Vercel CLIs plus `OPENAI_API_KEY` from an authorized operator. It is safe to rerun against the registered resources: migrations, canonical seed loading, environment-variable replacement, secret creation, and deployments converge instead of accumulating resources. Each run intentionally generates new high-entropy presenter and session secrets, so it is also a coordinated credential rotation. Normal pushes need no operator input because GitHub synchronizes the stored OpenAI key into Modal before deployment.

The script:

1. resolves pooled and direct TLS URLs for the registered Neon branches without printing them;
2. migrates, idempotently seeds, and verifies staging and hosted-production demo databases;
3. replaces Modal runtime/OpenAI secrets and matching GitHub environment secrets;
4. replaces Vercel Preview/Production API origins, public origin, demo-test flag, and protected presenter credential;
5. deploys Modal `main` and `staging` and verifies API plus Neon readiness;
6. invokes the repository AI attestation through the Responses API and fails closed unless OpenAI returns `gpt-5.6-luna` with low reasoning and a schema- plus semantic-valid body;
7. retains the freshly rotated presenter credential only in process memory while Playwright completes the seven-chapter journey against the Vercel production alias, including reset, persistence, pathology, messaging, denial recovery, MSO metrics, a final canonical reset, and logout.

`RUN_HOSTED_E2E=0` skips the final browser journey only for a deliberate infrastructure-only recovery operation; it is not a release attestation. Vercel masks sensitive values on environment pull, so the provisioner runs hosted E2E before discarding the generated presenter credential instead of copying that credential to disk. A passing hosted run leaves the canonical scenario at chapter one rather than leaving production in the completed test state.

This script is an infrastructure-maintainer operation, not contributor bootstrap. Product developers and new agents use `make dev` locally and Git for hosted previews; they do not handle connection strings or platform secrets.

## Vercel preview

The Vercel project is already linked to GitHub with Root Directory `apps/web`. A branch/PR push creates one native Vercel Preview; a `main` push creates a Production deployment. Preview server traffic rewrites to Modal `staging`, while the Production alias rewrites to Modal `main`.

`.github/workflows/vercel-preview.yml` has two responsibilities and no deployment credential:

1. on pull requests or manual dispatch, run `npm ci`, lint, typecheck, unit tests, and a production build;
2. on a successful non-production `deployment_status`, smoke the rendered root and `/api/health`, proving the Vercel-to-Modal-to-Neon path.

Require repository checks before merge and validate authentication/role policy, no-store headers, and the Sarah critical path on the exact preview. Vercel rollback re-points web traffic but cannot reverse Modal code or a Neon migration.

## Modal development and deployment

Official Modal CLI behavior: `modal serve` hot-reloads web functions and `modal deploy` creates/updates a persistent app. The managed `main` and `staging` environments contain `ambrosia-runtime` and the narrower `ambrosia-openai` secret. The current repository wrapper is addressed by `MODAL_APP_MODULE`.

```bash
# Authenticates the developer CLI once; do not use personal credentials in CI.
.venv/bin/modal setup

# Ephemeral development URL with hot reload.
MODAL_ENVIRONMENT=dev make modal-serve

# Tested persistent deployment.
MODAL_ENVIRONMENT=main make modal-deploy
MODAL_ENVIRONMENT=staging make modal-deploy
```

Direct one-off deployment is useful during development, but the reconciliation script is the authoritative way to rotate secrets, update Vercel bindings, and attest both managed environments. Verify direct unauthenticated domain requests fail even though the health endpoint intentionally exposes only bounded readiness state.

The CPU-only domain API uses Modal's scale-to-zero defaults. OpenAI timeout or provider failure selects the visible deterministic inference fallback; live and fallback proposals retain the same schema validation and clinician approval gate.

`.github/workflows/modal-deploy.yml` performs this gate independently for Modal `main` and `staging`: frozen-migration checksum → install/check/test → Neon migration → exact OpenAI model/reasoning/schema attestation → OpenAI-secret synchronization → tagged deploy → API/database/AI-configuration health. Every repository `main` push and manual dispatch reconciles both environments; Vercel production uses Modal `main`, while previews use `staging`. CI uses the installed-CLI-compatible form `modal deploy -m <module> --env <environment> --tag <sha>`.

## Release ordering

For a compatible change:

```mermaid
flowchart LR
    C["CI: lint · unit · build · integration"] --> E["Expand schema migration"]
    E --> M["Deploy Modal API/workers"]
    M --> S["API + workflow smoke tests"]
    S --> V["Deploy/test Vercel preview"]
    V --> P["Promote tested web artifact"]
    P --> O["Observe + reconcile"]
    O --> K["Later contract migration"]
```

- Migrations are backward compatible with both old and new Modal/API versions and any active browser session.
- A deploy never combines a destructive migration with code requiring it immediately. Backfill in durable, observable batches.
- Workers tolerate old/new event payload versions during the rollout.
- Health means database connectivity, migration compatibility and required adapters/seed state—not that downstream clinical results are safe to discard.

## Smoke gates

After each hosted deployment:

1. Modal `GET /api/health` reports process and database readiness without secrets or patient data.
2. Web `/api/health` proves the Vercel-to-Modal path, not a static success object.
3. An unauthenticated protected API call fails; each seeded role can reach only its allowed surface.
4. Patient-specific responses include `Cache-Control: private, no-store` and do not appear in Vercel shared cache.
5. Canonical scenario health verifies Sarah, appointment, open/closed work and seed version—not just row count.
6. Authenticated inference proves exact provider/model revision/prompt provenance and a schema-valid body; no missing/untrusted header may be recorded as live.
7. Forced AI timeout or invalid output produces a labeled deterministic proposal without bypassing review, and durable workflows show no stuck lease.
8. Synthetic provider duplicate event does not duplicate a result, payment, message or claim transition.

## Rollback and recovery

- **Vercel:** `vercel rollback [deployment]` or promote the last known-good deployment. Confirm its API/schema compatibility first.
- **Modal:** check out the known-good commit and redeploy the same module/tag to the same environment. Modal deployment rollback does not roll back Neon.
- **Database:** prefer forward fixes. Never run destructive downgrade against production data without a reviewed, tested recovery plan and backup/restore evidence.
- **External side effects:** code rollback cannot unsend a message/claim/result/payment. Reconcile from `integration_events`, provider IDs and durable tasks before retrying.
- **AI:** disable the affected live capability/model and route to safe manual/fallback behavior; preserve run/provenance for investigation.

Record deploy SHA, Vercel URL, Modal app/tag, migration revision, Neon branch, smoke results and approver in the release evidence register.

## Integration-sensitive commands

The repository command contract is `ambrosia-db migrate|seed|reset|verify`, `ambrosia-ai-attest`, Uvicorn import `app.main:app`, Modal module `backend.modal_app`, backend readiness `/api/health`, presenter health `/api/demo/health`, and web `lint|typecheck|test|build|e2e` scripts. After any topology, project, branch, endpoint, secret-name, model, or reasoning change, update the registry and reconciliation script together and rerun the full attestation rather than adding ad hoc alternatives.

References: [Vercel deployments](https://vercel.com/docs/deployments), [Vercel Git integration](https://vercel.com/docs/git), [Modal deploy CLI](https://modal.com/docs/cli/latest/deploy), [Modal development with `serve`](https://modal.com/docs/guide/developing-debugging), and [Modal ASGI web functions](https://modal.com/docs/guide/webhooks).
