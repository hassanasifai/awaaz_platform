# Awaaz Platform — developer tasks
# All commands assume `make` is run from the repo root.

SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON := python
COMPOSE := docker compose
COMPOSE_GPU := docker compose -f docker-compose.yml -f docker-compose.gpu.yml

# ----------------------------------------------------------------------------
# Help
# ----------------------------------------------------------------------------
.PHONY: help
help: ## Show this help.
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1;36m%-26s\033[0m %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------------
.PHONY: bootstrap
bootstrap: ## Install all language toolchains (Python venvs + node deps + pre-commit).
	cd apps/api && $(PYTHON) -m pip install -e .[dev]
	cd apps/agent && $(PYTHON) -m pip install -e .[dev]
	cd apps/dashboard && npm install
	cd apps/shopify-app && npm install
	pre-commit install

.PHONY: env
env: ## Copy .env.example to .env if not present.
	@test -f .env || cp .env.example .env && echo ".env created — fill it in."

# ----------------------------------------------------------------------------
# Compose
# ----------------------------------------------------------------------------
.PHONY: up
up: ## Bring up the cloud-only stack.
	$(COMPOSE) up -d --build

.PHONY: up-gpu
up-gpu: ## Bring up the GPU/local stack overlay.
	$(COMPOSE_GPU) up -d --build

.PHONY: down
down: ## Stop and remove all containers.
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail logs from every service.
	$(COMPOSE) logs -f --tail=200

.PHONY: ps
ps: ## Show container status.
	$(COMPOSE) ps

# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
.PHONY: db-migrate
db-migrate: ## Run Alembic migrations.
	cd apps/api && alembic upgrade head

.PHONY: db-revision
db-revision: ## Generate a new Alembic revision (use M="message").
	cd apps/api && alembic revision --autogenerate -m "$(M)"

.PHONY: db-seed
db-seed: ## Seed development data.
	cd apps/api && $(PYTHON) scripts/seed_dev.py

.PHONY: db-shell
db-shell: ## Open a psql shell against the dev DB.
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-awaaz} -d $${POSTGRES_DB:-awaaz}

# ----------------------------------------------------------------------------
# Lint / type-check / test
# ----------------------------------------------------------------------------
.PHONY: lint
lint: ## Run all linters.
	cd apps/api    && ruff check . && black --check . && mypy .
	cd apps/agent  && ruff check . && black --check . && mypy .
	cd apps/dashboard && npm run lint

.PHONY: format
format: ## Auto-format Python and TS.
	cd apps/api    && ruff check --fix . && black .
	cd apps/agent  && ruff check --fix . && black .
	cd apps/dashboard && npm run format

.PHONY: test
test: ## Run all tests.
	cd apps/api    && pytest -q
	cd apps/agent  && pytest -q
	cd apps/dashboard && npm test --silent

.PHONY: test-unit
test-unit: ## Run unit tests only.
	cd apps/api   && pytest -q -m "not integration and not eval"
	cd apps/agent && pytest -q -m "not integration and not eval"

.PHONY: eval
eval: ## Run the LLM eval suite.
	cd apps/agent && $(PYTHON) scripts/run_eval_suite.py

# ----------------------------------------------------------------------------
# Test conversation / call helpers
# ----------------------------------------------------------------------------
.PHONY: test-wa
test-wa: ## Send a test WhatsApp template (PHONE=+923XXXXXXXXX, ORDER_ID=...).
	cd apps/api && $(PYTHON) scripts/make_test_conversation.py --phone "$(PHONE)" --order-id "$(ORDER_ID)"

.PHONY: test-call
test-call: ## Place a test voice call (voice channel; requires FEATURE_VOICE_CHANNEL=true).
	cd apps/api && $(PYTHON) scripts/make_test_call.py --phone "$(PHONE)" --order-id "$(ORDER_ID)"

# ----------------------------------------------------------------------------
# Shipping
# ----------------------------------------------------------------------------
.PHONY: build
build: ## Build all production images.
	$(COMPOSE) -f docker-compose.prod.yml build

.PHONY: clean
clean: ## Remove build artefacts and caches.
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache"  -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache"  -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next"        -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
