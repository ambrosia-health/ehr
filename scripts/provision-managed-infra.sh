#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NEON_PROJECT_ID="round-cloud-23718842"
NEON_DATABASE="ambrosia"
NEON_ROLE="ambrosia_owner"
STAGING_BRANCH="br-rough-feather-auv415ro"
PRODUCTION_BRANCH="br-still-wildflower-aunolqvx"
GITHUB_REPOSITORY="ambrosia-health/ehr"
VERCEL_ORG_ID="team_NWSCGbaTw7YBdtMacOBB2f2D"
VERCEL_PROJECT_ID="prj_ad1AsXV5muySOAyBsxMgcKAj1SVa"
STAGING_API="https://kshr-ai-staging--ambrosia-health-domain-api-api.modal.run"
STAGING_AI="https://kshr-ai-staging--structured-inference.modal.run"
PRODUCTION_API="https://kshr-ai-production--ambrosia-health-domain-api-api.modal.run"
PRODUCTION_AI="https://kshr-ai-production--structured-inference.modal.run"
WEB_ORIGIN="https://ambrosia-ehr.vercel.app"

for command in gh neonctl node npm openssl uv; do
  command -v "$command" >/dev/null || {
    echo "$command is required to provision managed infrastructure" >&2
    exit 1
  }
done

make backend-install web-install >/dev/null

presenter="$(openssl rand -hex 24)"
staging_session="$(openssl rand -hex 32)"
production_session="$(openssl rand -hex 32)"
staging_internal="$(openssl rand -hex 32)"
production_internal="$(openssl rand -hex 32)"

neon_url() {
  local branch="$1"
  local pooled="$2"
  local args=(
    connection-string "$branch"
    --project-id "$NEON_PROJECT_ID"
    --database-name "$NEON_DATABASE"
    --role-name "$NEON_ROLE"
    --ssl require
    --no-color
  )
  if [[ "$pooled" == "true" ]]; then
    args+=(--pooled)
  fi
  neonctl "${args[@]}"
}

staging_db="$(neon_url "$STAGING_BRANCH" true)"
production_db="$(neon_url "$PRODUCTION_BRANCH" true)"
staging_direct="$(neon_url "$STAGING_BRANCH" false)"
production_direct="$(neon_url "$PRODUCTION_BRANCH" false)"
[[ "$staging_db" == postgresql://* ]]
[[ "$production_db" == postgresql://* ]]

for database_url in "$staging_direct" "$production_direct"; do
  DATABASE_URL="$database_url" .venv/bin/ambrosia-db migrate >/dev/null
  DATABASE_URL="$database_url" .venv/bin/ambrosia-db seed >/dev/null
  DATABASE_URL="$database_url" .venv/bin/ambrosia-db verify >/dev/null
done
echo "Neon staging and production are migrated, seeded, and verified."

common_runtime=(
  "DEMO_PRESENTER_SECRET=$presenter"
  "DEMO_MODE=true"
  "EXECUTION_PLATFORM=modal"
  "SESSION_COOKIE_SECURE=true"
  "SESSION_COOKIE_NAME=__Host-ambrosia_session"
  "ALLOW_SYNTHETIC_DEMO_RESET=true"
  "AUTO_CREATE_SCHEMA=false"
  "AUTO_SEED=false"
  "CORS_ORIGINS=[\"$WEB_ORIGIN\"]"
  "AI_REQUEST_TIMEOUT_SECONDS=8"
  "ELIGIBILITY_PROVIDER=simulated"
  "CLEARINGHOUSE_PROVIDER=simulated"
  "REMITTANCE_PROVIDER=simulated"
  "MESSAGING_PROVIDER=simulated"
  "EPRESCRIBING_PROVIDER=simulated"
  "PATHOLOGY_PROVIDER=simulated"
  "PAYMENT_PROVIDER=simulated"
)

.venv/bin/modal secret create ambrosia-runtime --env staging --force \
  "APP_ENV=staging" \
  "DATABASE_URL=$staging_db" \
  "AUTH_SESSION_SECRET=$staging_session" \
  "MODAL_INTERNAL_AUTH_SECRET=$staging_internal" \
  "MODAL_AI_URL=$STAGING_AI" \
  "${common_runtime[@]}" >/dev/null
.venv/bin/modal secret create ambrosia-ai-internal --env staging --force \
  "MODAL_INTERNAL_AUTH_SECRET=$staging_internal" >/dev/null
.venv/bin/modal secret create ambrosia-runtime --env production --force \
  "APP_ENV=production" \
  "DATABASE_URL=$production_db" \
  "AUTH_SESSION_SECRET=$production_session" \
  "MODAL_INTERNAL_AUTH_SECRET=$production_internal" \
  "MODAL_AI_URL=$PRODUCTION_AI" \
  "${common_runtime[@]}" >/dev/null
.venv/bin/modal secret create ambrosia-ai-internal --env production --force \
  "MODAL_INTERNAL_AUTH_SECRET=$production_internal" >/dev/null

printf '%s' "$staging_internal" | gh secret set MODAL_INTERNAL_AUTH_SECRET --env staging -R "$GITHUB_REPOSITORY"
printf '%s' "$STAGING_AI" | gh secret set MODAL_AI_URL --env staging -R "$GITHUB_REPOSITORY"
printf '%s' "$STAGING_API/api/health" | gh secret set MODAL_API_HEALTH_URL --env staging -R "$GITHUB_REPOSITORY"
printf '%s' "$staging_direct" | gh secret set NEON_DATABASE_URL_DIRECT --env staging -R "$GITHUB_REPOSITORY"
printf '%s' "$presenter" | gh secret set PRESENTER_ACCESS_CODE --env staging -R "$GITHUB_REPOSITORY"
printf '%s' "$production_internal" | gh secret set MODAL_INTERNAL_AUTH_SECRET --env production -R "$GITHUB_REPOSITORY"
printf '%s' "$PRODUCTION_AI" | gh secret set MODAL_AI_URL --env production -R "$GITHUB_REPOSITORY"
printf '%s' "$PRODUCTION_API/api/health" | gh secret set MODAL_API_HEALTH_URL --env production -R "$GITHUB_REPOSITORY"
printf '%s' "$production_direct" | gh secret set NEON_DATABASE_URL_DIRECT --env production -R "$GITHUB_REPOSITORY"
printf '%s' "$presenter" | gh secret set PRESENTER_ACCESS_CODE --env production -R "$GITHUB_REPOSITORY"
echo "Modal and GitHub environment secrets are synchronized."

export VERCEL_ORG_ID VERCEL_PROJECT_ID
for target in production preview; do
  printf '%s' "$presenter" | npx --yes vercel@56.3.0 --cwd apps/web env add \
    PRESENTER_ACCESS_CODE "$target" --force --sensitive --yes >/dev/null
done
printf '%s' "$presenter" | npx --yes vercel@56.3.0 --cwd apps/web env add \
  PRESENTER_ACCESS_CODE development --force --no-sensitive --yes >/dev/null
npx --yes vercel@56.3.0 --cwd apps/web env add AMBROSIA_API_ORIGIN preview \
  --force --no-sensitive --value "$STAGING_API" --yes >/dev/null
npx --yes vercel@56.3.0 --cwd apps/web env add AMBROSIA_API_ORIGIN production \
  --force --no-sensitive --value "$PRODUCTION_API" --yes >/dev/null
for target in production preview development; do
  npx --yes vercel@56.3.0 --cwd apps/web env add NEXT_PUBLIC_APP_URL "$target" \
    --force --no-sensitive --value "$WEB_ORIGIN" --yes >/dev/null
  npx --yes vercel@56.3.0 --cwd apps/web env add NEXT_PUBLIC_DEMO_TEST_MODE "$target" \
    --force --no-sensitive --value false --yes >/dev/null
done
echo "Vercel environment bindings are synchronized."

prompt='Ambrosia chart_summary prompt. Use minimum necessary context and return schema-valid JSON.'
prompt_hash="$(printf '%s' "$prompt" | shasum -a 256 | cut -d ' ' -f 1)"
payload="$(
  PROMPT="$prompt" PROMPT_HASH="$prompt_hash" python3 -c \
    'import json, os; print(json.dumps({"capability":"chart_summary","context":{"patientName":"Synthetic readiness patient"},"prompt":{"version":"2026.1","template":os.environ["PROMPT"],"sha256":os.environ["PROMPT_HASH"]}}))'
)"

deploy_and_attest() {
  local environment="$1"
  local api_url="$2"
  local ai_url="$3"
  local internal_secret="$4"
  local headers
  local body
  headers="$(mktemp)"
  body="$(mktemp)"

  .venv/bin/modal deploy -m backend.modal_app --env "$environment"
  curl --fail --silent --show-error --retry 10 --retry-all-errors --retry-delay 3 \
    --max-time 30 "$api_url/api/health" |
    python3 -c 'import json, sys; data=json.load(sys.stdin); assert data.get("status")=="healthy" and data.get("database")=="healthy", data'

  for attempt in 1 2; do
    : >"$headers"
    : >"$body"
    curl --fail --silent --show-error --max-time 175 \
      --dump-header "$headers" \
      --output "$body" \
      -H "X-Ambrosia-Internal: $internal_secret" \
      -H 'Content-Type: application/json' \
      --data "$payload" \
      "$ai_url" || true
    if grep -Fqi 'x-ambrosia-ai-provider: modal_open_weights' "$headers" && \
      grep -Fqi 'x-ambrosia-ai-fallback: false' "$headers" && \
      grep -Fqi 'x-ambrosia-ai-model: Qwen/Qwen2.5-0.5B-Instruct@7ae557604adf67be50417f59c2c2f167def9a775' "$headers" && \
      grep -Fqi "x-ambrosia-ai-prompt-hash: $prompt_hash" "$headers" && \
      BODY="$body" python3 -c 'import json, os; data=json.load(open(os.environ["BODY"])); assert data.get("headline") and data.get("activeConcerns")'; then
      echo "$environment API, Neon connection, live-model provenance, and output schema are attested."
      return 0
    fi
    echo "$environment live-model attempt $attempt returned fallback or incomplete attestation."
  done

  echo "$environment live-model attestation failed" >&2
  grep -i '^x-ambrosia-ai-' "$headers" >&2 || true
  return 1
}

deploy_and_attest staging "$STAGING_API" "$STAGING_AI" "$staging_internal"
deploy_and_attest production "$PRODUCTION_API" "$PRODUCTION_AI" "$production_internal"

if [[ "${RUN_HOSTED_E2E:-1}" == "1" ]]; then
  (
    cd apps/web
    npx playwright install chromium >/dev/null
  )
  E2E_LIVE_API=1 \
    E2E_TIMEOUT_MS=1200000 \
    PRESENTER_ACCESS_CODE="$presenter" \
    NEXT_PUBLIC_APP_URL="$WEB_ORIGIN" \
    npm --prefix apps/web run e2e:hosted
  echo "Hosted seven-chapter synthetic journey is attested."
fi
echo "Managed Ambrosia infrastructure is provisioned and attested."
