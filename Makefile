COMPOSE ?= docker compose
BACKEND_SERVICE ?= backend

PYTEST_ARGS ?=
MIGRATE_ARGS ?=
SEED_ARGS ?=
LOGS_SERVICE ?=

.PHONY: help init-env check-uv up down build restart reset ps logs test test-subset migrate seed shell clean

help:
	@echo "Available targets:"
	@echo "  make init-env          # Create .env from .env.example if needed"
	@echo "  make check-uv          # Verify local uv is installed"
	@echo "  make up                # Build and start stack in background"
	@echo "  make down              # Stop stack"
	@echo "  make build             # Build images"
	@echo "  make restart           # Restart stack (down + up)"
	@echo "  make reset             # Full reset: clean + up + migrate + seed"
	@echo "  make ps                # Show service status"
	@echo "  make logs              # Show logs (set LOGS_SERVICE=backend)"
	@echo "  make test [paths...]   # Run backend tests, optional positional test paths"
	@echo "  make test-subset [paths...] # Run subset without global coverage gate"
	@echo "                         # Add pytest flags with PYTEST_ARGS='-q -k auth'"
	@echo "  make migrate           # Run alembic upgrade head (set MIGRATE_ARGS='--sql')"
	@echo "  make seed              # Run seed script (set SEED_ARGS='--help' if script supports it)"
	@echo "  make shell             # Open shell in backend container"
	@echo "  make clean             # Stop stack and remove volumes"

init-env:
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; else echo ".env already exists"; fi

check-uv:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

restart: down up

reset: clean up migrate seed

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f $(LOGS_SERVICE)

test: check-uv
	cd backend && uv run pytest $(PYTEST_ARGS) $(filter-out $@,$(MAKECMDGOALS))

test-subset: check-uv
	cd backend && uv run pytest --override-ini addopts= $(PYTEST_ARGS) $(filter-out $@,$(MAKECMDGOALS))

migrate:
	$(COMPOSE) run --rm $(BACKEND_SERVICE) uv run alembic upgrade head $(MIGRATE_ARGS)

seed:
	$(COMPOSE) run --rm $(BACKEND_SERVICE) uv run python -m scripts.seed_data $(SEED_ARGS)

shell:
	$(COMPOSE) run --rm $(BACKEND_SERVICE) sh

clean:
	$(COMPOSE) down -v

%:
	@:
