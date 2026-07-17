SHELL := /bin/bash
.DEFAULT_GOAL := help
.NOTPARALLEL:

WEB_DIR ?= apps/web
BACKEND_DIR ?= backend
VENV ?= .venv
UV ?= uv
NODE ?= node
NPM ?= npm
NPX ?= npx
UV_PROJECT_ENVIRONMENT ?= $(abspath $(VENV))
PY := $(VENV)/bin/python
HOST ?= 127.0.0.1
API_PORT ?= 8000
WEB_PORT ?= 3000
AMBROSIA_API_ORIGIN ?= http://127.0.0.1:8000
NEXT_PUBLIC_APP_URL ?= http://localhost:3000
MODAL_ENVIRONMENT ?= dev
MODAL_APP_MODULE ?= backend.modal_app
POSTGRES_DATABASE_URL ?= postgresql+asyncpg://ambrosia:ambrosia-local-only@127.0.0.1:5432/ambrosia

# Let an existing local template override command defaults while keeping backend
# configuration in pydantic-settings. Only browser build variables need export.
-include .env
export AMBROSIA_API_ORIGIN NEXT_PUBLIC_APP_URL DEMO_PRESENTER_SECRET

.PHONY: help env check-tools check-uv check-npm bootstrap bootstrap-ci web-install backend-install db-up db-down db-wait \
	migrate seed reset verify-data dev dev-postgres dev-services test test-postgres test-backend test-web e2e e2e-run check web-check backend-check \
	demo-health modal-serve modal-deploy clean

help: ## List supported workflows.
	@awk 'BEGIN {FS = ":.*## "; printf "Ambrosia workflows\n\n"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

env: ## Create .env from the synthetic-safe template when absent.
	@test -f .env || cp .env.example .env
	@mkdir -p .ambrosia

check-tools: check-uv check-npm ## Fail clearly unless npm and uv are installed.

check-uv: ## Fail clearly unless uv is installed.
	@command -v $(UV) >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv" >&2; exit 1; }

check-npm: ## Fail clearly unless Node.js/npm are installed.
	@command -v $(NODE) >/dev/null 2>&1 || { echo "Node.js 22–24 is required: https://nodejs.org" >&2; exit 1; }
	@command -v $(NPM) >/dev/null 2>&1 || { echo "Node.js 22–24 with npm is required: https://nodejs.org" >&2; exit 1; }
	@command -v $(NPX) >/dev/null 2>&1 || { echo "npx is required with npm" >&2; exit 1; }
	@$(NODE) -e 'const major=Number(process.versions.node.split(".")[0]); if (major < 22 || major >= 25) { console.error(`Node.js 22–24 is required; found $${process.versions.node}`); process.exit(1) }'

backend-install: check-uv ## Sync the locked backend environment with uv.
	UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" $(UV) sync --project $(BACKEND_DIR) --extra dev --locked

web-install: check-npm ## Install the locked frontend dependency graph.
	@test -f "$(WEB_DIR)/package-lock.json" || { echo "$(WEB_DIR)/package-lock.json is required" >&2; exit 1; }
	$(NPM) --prefix $(WEB_DIR) ci

bootstrap: env backend-install web-install migrate seed verify-data ## Prepare a complete zero-credential SQLite environment.

bootstrap-ci: backend-install web-install ## Install locked dependencies without starting services.

db-up: ## Start the disposable local Postgres service.
	docker compose up -d postgres

db-down: ## Stop local Postgres without deleting its volume.
	docker compose down

db-wait: ## Wait until local Postgres accepts connections.
	@for attempt in $$(seq 1 30); do \
		if docker compose exec -T postgres sh -c 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' >/dev/null 2>&1; then exit 0; fi; \
		sleep 1; \
	done; \
	echo "Postgres did not become ready" >&2; exit 1

migrate: ## Apply migration-controlled schema changes.
	$(VENV)/bin/ambrosia-db migrate

seed: ## Idempotently load the canonical synthetic scenario.
	$(VENV)/bin/ambrosia-db seed

reset: env backend-install migrate ## Reset only the configured synthetic environment, then reseed it.
	$(VENV)/bin/ambrosia-db reset
	$(VENV)/bin/ambrosia-db verify

verify-data: ## Check canonical seed counts, relationships, and financial invariants.
	$(VENV)/bin/ambrosia-db verify

dev: bootstrap ## Start FastAPI and Next.js; Ctrl-C stops both.
	@$(MAKE) --no-print-directory dev-services

dev-postgres: env backend-install web-install db-up db-wait ## Run locally against Docker Postgres 16.
	@DATABASE_URL=$(POSTGRES_DATABASE_URL) $(MAKE) --no-print-directory migrate seed verify-data
	@DATABASE_URL=$(POSTGRES_DATABASE_URL) $(MAKE) --no-print-directory dev-services

dev-services:
	@set -euo pipefail; \
		$(PY) -m uvicorn app.main:app --reload --reload-dir $(BACKEND_DIR)/app --host $(HOST) --port $(API_PORT) & api_pid=$$!; \
		AMBROSIA_API_ORIGIN="$(AMBROSIA_API_ORIGIN)" NEXT_PUBLIC_APP_URL="$(NEXT_PUBLIC_APP_URL)" $(NPM) --prefix $(WEB_DIR) run dev -- --hostname $(HOST) --port $(WEB_PORT) & web_pid=$$!; \
		trap 'kill $$api_pid $$web_pid 2>/dev/null || true' EXIT INT TERM; \
		while kill -0 $$api_pid 2>/dev/null && kill -0 $$web_pid 2>/dev/null; do sleep 1; done; \
		wait $$api_pid $$web_pid 2>/dev/null || true; \
		exit 1

test: backend-install web-install test-backend test-web ## Run backend and frontend deterministic test suites.

test-postgres: backend-install db-up db-wait ## Run migrations, seed, and backend tests against Docker Postgres.
	@APP_ENV=test DATABASE_URL=$(POSTGRES_DATABASE_URL) ALLOW_TEST_DATABASE_RESET=true $(MAKE) --no-print-directory migrate seed verify-data test-backend

test-backend:
	$(PY) -m pytest $(BACKEND_DIR)/tests

test-web:
	$(NPM) --prefix $(WEB_DIR) run test

e2e: env check-npm ## Run Playwright against the running local synthetic stack.
	@$(MAKE) --no-print-directory e2e-run

e2e-run:
	@set -euo pipefail; \
		(cd "$(WEB_DIR)" && $(NPX) playwright install chromium >/dev/null); \
		$(NPM) --prefix $(WEB_DIR) run e2e

backend-check:
	$(PY) -m ruff check $(BACKEND_DIR)

web-check:
	$(NPM) --prefix $(WEB_DIR) run lint
	$(NPM) --prefix $(WEB_DIR) run typecheck
	$(NPM) --prefix $(WEB_DIR) run test
	AMBROSIA_API_ORIGIN="$(AMBROSIA_API_ORIGIN)" NEXT_PUBLIC_APP_URL="$(NEXT_PUBLIC_APP_URL)" $(NPM) --prefix $(WEB_DIR) run build

check: backend-install web-install backend-check web-check test-backend ## Run the static, build, and unit checks used by CI.

demo-health: ## Verify web/API health and the protected seeded scenario.
	@set -euo pipefail; \
		test -n "$${DEMO_PRESENTER_SECRET:-}" || { echo "DEMO_PRESENTER_SECRET is required in .env" >&2; exit 1; }; \
		cookie_jar="$$(mktemp)"; \
		trap 'rm -f "$$cookie_jar"' EXIT; \
		curl --fail --silent --show-error http://$(HOST):$(API_PORT)/api/health | \
			$(PY) -c 'import json, sys; data = json.load(sys.stdin); assert data.get("status") == "healthy" and data.get("database") == "healthy", data'; \
		curl --fail --silent --show-error http://$(HOST):$(WEB_PORT)/api/health | \
			$(PY) -c 'import json, sys; data = json.load(sys.stdin); assert data.get("status") == "healthy" and data.get("database") == "healthy", data'; \
		payload="$$( $(PY) -c 'import json, os; print(json.dumps({"persona": "owner", "presenter_code": os.environ["DEMO_PRESENTER_SECRET"]}))' )"; \
		curl --fail --silent --show-error --cookie-jar "$$cookie_jar" \
			-H 'Content-Type: application/json' --data "$$payload" \
			http://$(HOST):$(WEB_PORT)/api/auth/demo/session >/dev/null; \
		curl --fail --silent --show-error --cookie "$$cookie_jar" \
			http://$(HOST):$(WEB_PORT)/api/demo/health | \
			$(PY) -c 'import json, sys; data = json.load(sys.stdin); assert data.get("status") in {"healthy", "degraded"} and data.get("scenario") and data.get("counts") and data.get("database") in {"sqlite_local", "neon_postgres"}, data'; \
		echo "API, same-origin rewrite, and protected canonical scenario are ready (AI fallback may report degraded)."

modal-serve: backend-install ## Hot-reload the Modal ASGI wrapper in the configured environment.
	$(VENV)/bin/modal serve -m $(MODAL_APP_MODULE) --env $(MODAL_ENVIRONMENT)

modal-deploy: backend-install check ## Deploy the tested Modal app.
	$(VENV)/bin/modal deploy -m $(MODAL_APP_MODULE) --env $(MODAL_ENVIRONMENT)

clean: ## Remove generated local build/test state but preserve database data.
	rm -rf $(VENV) $(WEB_DIR)/.next coverage htmlcov .pytest_cache .ruff_cache
