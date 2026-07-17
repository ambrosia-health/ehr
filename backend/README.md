# Ambrosia domain API

FastAPI + SQLAlchemy domain service for the Ambrosia Health synthetic dermatology operating system. Neon Postgres is the durable deployment target; async SQLite is the zero-configuration local and test fallback.

> **Synthetic data only.** The deployed API and inference services are demo infrastructure, not approved endpoints for real PHI, clinical care, live integrations, or autonomous decisions.

## Local development

Requires uv; the locked environment provisions Python 3.12 or newer.

From the repository root, `make dev` is the preferred zero-credential bootstrap: it creates the safe local configuration, migrates/seeds SQLite, and starts this API plus the web app. For backend-only work:

```bash
UV_PROJECT_ENVIRONMENT="$PWD/.venv" uv sync --project backend --extra dev --locked
cd backend
alembic upgrade head
ambrosia-db seed
uvicorn app.main:app --reload --port 8000
```

The API and OpenAPI document are served at `/api` and `/api/docs`. Demo login creates an HttpOnly, signed `ambrosia_session` cookie. `X-Demo-Persona` is accepted only when `APP_ENV=test`.

## Database commands

```bash
ambrosia-db migrate
ambrosia-db seed
ambrosia-db reset
ambrosia-db verify
```

`reset` is limited to the canonical synthetic organization. In production it additionally requires `ALLOW_SYNTHETIC_DEMO_RESET=true` and a protected presenter session when called over HTTP.

## Core environment

- `DATABASE_URL` or `NEON_DATABASE_URL`: asyncpg-compatible Neon URL; defaults to local SQLite.
- `APP_ENV`: `development`, `test`, or `production`.
- `AUTH_SESSION_SECRET`: required and non-default in production.
- `DEMO_PRESENTER_SECRET`: required and non-default in production.
- `SESSION_COOKIE_SECURE`: set `true` behind HTTPS.
- `CORS_ORIGINS`: comma-separated explicit browser origins.
- `OPENAI_API_KEY`: managed hosted secret used only by the Modal domain API; absent, timed-out, malformed, semantically unsafe, or unattested output selects the schema-validated deterministic fallback.
- `AI_REQUEST_TIMEOUT_SECONDS`: OpenAI request timeout, default 8 seconds locally and 60 seconds in managed environments.
- `ALLOW_SYNTHETIC_DEMO_RESET`: explicit production-only reset guard.

## Managed hosted runtime

Modal environments `main` and `staging` expose the domain API at:

- `https://kshr-ai--ambrosia-health-domain-api-api.modal.run`
- `https://kshr-ai-staging--ambrosia-health-domain-api-api.modal.run`

Inference uses OpenAI `gpt-5.6-luna` through the Responses API with low reasoning and `store=false`. The domain API has no GPU allocation, local model weights, or separate inference endpoint. Generated JSON is parsed into the capability schema and then checked against semantic safety rules before it can be recorded as a live proposal. Failures use `ambrosia-fixture-2026.1`, set fallback provenance, and retain the same human gate.

[`../scripts/provision-managed-infra.sh`](../scripts/provision-managed-infra.sh) is the authorized, rerunnable reconciliation path for database migration/seed verification, environment-secret synchronization, Modal deployment, API/database health, and OpenAI model-contract attestation. Local contributors do not need its cloud credentials.

## FHIR adapter boundary

The internal model is domain-first, not a FHIR replica. A future adapter maps `Patient`, `Appointment`, `Encounter`, `Observation` (lesion observations), `DocumentReference` (file metadata), `DiagnosticReport`/`Specimen`, `Claim`/`ExplanationOfBenefit`, and `Provenance`/`AuditEvent` at the integration boundary. Source identifiers and adapter payloads belong in `integration_events`; clinical mutations still pass through the domain service and audit trail.
