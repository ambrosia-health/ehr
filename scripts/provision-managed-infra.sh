#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NEON_PROJECT_ID="round-cloud-23718842"
NEON_DATABASE="ambrosia"
NEON_ROLE="ambrosia_owner"
MAIN_BRANCH="br-still-wildflower-aunolqvx"
STAGING_BRANCH="br-rough-feather-auv415ro"
GITHUB_REPOSITORY="ambrosia-health/ehr"
MAIN_API="https://kshr-ai--ambrosia-health-domain-api-api.modal.run"
STAGING_API="https://kshr-ai-staging--ambrosia-health-domain-api-api.modal.run"
WEB_ORIGIN="https://ambrosia-ehr.vercel.app"

: "${OPENAI_API_KEY:?OPENAI_API_KEY must be supplied by an authorized platform operator}"

for command in gh neonctl node npm openssl uv; do
  command -v "$command" >/dev/null || {
    echo "$command is required to provision managed infrastructure" >&2
    exit 1
  }
done

make backend-install web-install >/dev/null

presenter="$(openssl rand -hex 24)"
main_session="$(openssl rand -hex 32)"
staging_session="$(openssl rand -hex 32)"

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

main_db="$(neon_url "$MAIN_BRANCH" true)"
main_direct="$(neon_url "$MAIN_BRANCH" false)"
staging_db="$(neon_url "$STAGING_BRANCH" true)"
staging_direct="$(neon_url "$STAGING_BRANCH" false)"
[[ "$main_db" == postgresql://* ]]
[[ "$staging_db" == postgresql://* ]]

for database_url in "$main_direct" "$staging_direct"; do
  DATABASE_URL="$database_url" .venv/bin/ambrosia-db migrate >/dev/null
  DATABASE_URL="$database_url" .venv/bin/ambrosia-db seed >/dev/null
  DATABASE_URL="$database_url" .venv/bin/ambrosia-db verify >/dev/null
done
echo "Neon main and staging are migrated, seeded, and verified."

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
  "AI_REQUEST_TIMEOUT_SECONDS=60"
  "ELIGIBILITY_PROVIDER=simulated"
  "CLEARINGHOUSE_PROVIDER=simulated"
  "REMITTANCE_PROVIDER=simulated"
  "MESSAGING_PROVIDER=simulated"
  "EPRESCRIBING_PROVIDER=simulated"
  "PATHOLOGY_PROVIDER=simulated"
  "PAYMENT_PROVIDER=simulated"
)

.venv/bin/modal secret create ambrosia-runtime --env main --force \
  "APP_ENV=production" \
  "DATABASE_URL=$main_db" \
  "AUTH_SESSION_SECRET=$main_session" \
  "${common_runtime[@]}" >/dev/null
.venv/bin/modal secret create ambrosia-openai --env main --force \
  "OPENAI_API_KEY=$OPENAI_API_KEY" >/dev/null
.venv/bin/modal secret create ambrosia-runtime --env staging --force \
  "APP_ENV=staging" \
  "DATABASE_URL=$staging_db" \
  "AUTH_SESSION_SECRET=$staging_session" \
  "${common_runtime[@]}" >/dev/null
.venv/bin/modal secret create ambrosia-openai --env staging --force \
  "OPENAI_API_KEY=$OPENAI_API_KEY" >/dev/null

printf '%s' "$MAIN_API/api/health" | gh secret set MODAL_API_HEALTH_URL --env production -R "$GITHUB_REPOSITORY"
printf '%s' "$main_direct" | gh secret set NEON_DATABASE_URL_DIRECT --env production -R "$GITHUB_REPOSITORY"
printf '%s' "$presenter" | gh secret set PRESENTER_ACCESS_CODE --env production -R "$GITHUB_REPOSITORY"
printf '%s' "$OPENAI_API_KEY" | gh secret set OPENAI_API_KEY --env production -R "$GITHUB_REPOSITORY"
printf '%s' "$STAGING_API/api/health" | gh secret set MODAL_API_HEALTH_URL --env staging -R "$GITHUB_REPOSITORY"
printf '%s' "$staging_direct" | gh secret set NEON_DATABASE_URL_DIRECT --env staging -R "$GITHUB_REPOSITORY"
printf '%s' "$presenter" | gh secret set PRESENTER_ACCESS_CODE --env staging -R "$GITHUB_REPOSITORY"
printf '%s' "$OPENAI_API_KEY" | gh secret set OPENAI_API_KEY --env staging -R "$GITHUB_REPOSITORY"
echo "Modal main/staging and GitHub production/staging secrets are synchronized."

deploy_and_attest() {
  local environment="$1"
  local api_url="$2"

  .venv/bin/modal deploy -m backend.modal_app --env "$environment"
  curl --fail --silent --show-error --retry 10 --retry-all-errors --retry-delay 3 \
    --max-time 30 "$api_url/api/health" |
    python3 -c 'import json, sys; data=json.load(sys.stdin); assert data.get("status")=="healthy" and data.get("database")=="healthy" and data.get("ai")=="openai_configured" and data.get("aiModel")=="gpt-5.6-luna" and data.get("aiReasoningEffort")=="low", data'
  .venv/bin/ambrosia-ai-attest
  echo "$environment API, Neon connection, and OpenAI model contract are attested."
}

deploy_and_attest main "$MAIN_API"
deploy_and_attest staging "$STAGING_API"

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
