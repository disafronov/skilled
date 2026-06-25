PYTHONPATH = src

# Python version is pinned via `.python-version` (used by uv and CI).
PYTHON_VERSION := $(shell tr -d '[:space:]' < .python-version)

# Include environment files (same pattern as other repos).
#
# Important: in CI, environment variables passed by the runner must win over
# defaults from `env.example`, but GNU make gives Makefile assignments higher
# priority than the environment. Therefore we only auto-include env files for
# local development (when `CI` is not set).
#
# - `env.example` provides defaults and documents available settings.
# - `.env` (if present) overrides `env.example` for local development.
ifeq ($(strip $(CI)),)
    ifneq (,$(wildcard .env))
        ifneq (,$(wildcard env.example))
            include env.example
        endif
        include .env
    else
        ifneq (,$(wildcard env.example))
            include env.example
        endif
    endif
    export
endif

# Tooling-only SECRET_KEY used for local checks.
#
# Django settings require SECRET_KEY when DEBUG is disabled. Both pytest-django and
# django-stubs (mypy) import Django settings during initialization, so we provide a
# deterministic fake key for local tooling via Makefile targets.
TOOLING_SECRET_KEY = unsafe-secret-key-for-tooling

UV = PYTHONPATH=$(PYTHONPATH) uv run
PYTEST_CMD = SECRET_KEY=$(TOOLING_SECRET_KEY) $(UV) python -m pytest -v
COVERAGE_OPTS = --cov-report=html

DOCKER_IMAGE = sloths-inventory

# Common flags for all docker run invocations (no port — added only for the server step).
DOCKER_RUN_OPTS = --rm \
	--read-only \
	--tmpfs /tmp \
	--add-host=host.docker.internal:host-gateway \
	$(if $(wildcard env.example),--env-file env.example,) \
	$(if $(wildcard env.docker),--env-file env.docker,) \
	$(if $(wildcard .env),--env-file .env,)

.PHONY: all audit clean dead-code dev docker docker-build docker-run format help install lint locale makemigrations migrate q2 run test

help: ## Show this help message
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

install: ## Install dependencies
	@echo "Installing dependencies..."
	uv python install $(PYTHON_VERSION)
	uv sync --python $(PYTHON_VERSION)
	@echo "Installing pre-commit hooks..."
	uv run pre-commit install

format: ## Format code
	@echo "Formatting code..."
	$(UV) black . && \
	$(UV) isort .

lint: ## Run linting tools
	@echo "Running linting tools..."
	$(UV) black --check . && \
	$(UV) isort --check-only . && \
	$(UV) flake8 . && \
	SECRET_KEY=$(TOOLING_SECRET_KEY) $(UV) mypy . && \
	$(UV) bandit -r -c pyproject.toml .

audit: ## Check dependencies for known vulnerabilities
	@echo "Auditing dependencies..."
	uv run pip-audit

dead-code: ## Check for dead code using vulture
	@echo "Checking for dead code..."
	uv run vulture

locale: ## Make & compile locale messages
	@echo "Make translation messages..."
	SECRET_KEY=$(TOOLING_SECRET_KEY) $(UV) python src/manage.py makemessages --no-obsolete --all --ignore=".venv/*" --ignore="*/tests/*" --ignore="conftest.py"
	@echo "Compile translation messages..."
	SECRET_KEY=$(TOOLING_SECRET_KEY) $(UV) python src/manage.py compilemessages --ignore=".venv/*"

makemigrations: ## Create new migrations
	@echo "Creating migrations..."
	SECRET_KEY=$(TOOLING_SECRET_KEY) $(UV) python src/manage.py makemigrations

migrate: ## Apply database migrations
	@echo "Applying migrations..."
	$(UV) python src/manage.py migrate

test: locale ## Run tests with coverage report
	@echo "Running tests with coverage..."
	$(PYTEST_CMD) $(COVERAGE_OPTS)

all: lint test dead-code ## Run all checks (no mutations)
	@echo "All checks completed successfully!"

dev: locale migrate ## Run qcluster + runserver together (manage.py dev)
	@echo "Running qcluster + dev server..."
	$(UV) python src/manage.py dev

q2: ## Run django-q2 worker (qcluster) without the web server
	@echo "Running django-q2 worker..."
	$(UV) python src/manage.py qcluster

run: locale migrate ## Run dev server + qcluster locally (mirrors Docker entrypoint)
	@echo "Running Django dev server + qcluster locally..."
	@if [ -n "$$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$$DJANGO_SUPERUSER_EMAIL" ]; then \
		echo "Ensuring Django superuser exists..."; \
		$(UV) python src/manage.py createsuperuser --noinput || true; \
	else \
		echo "Skipping createsuperuser (set DJANGO_SUPERUSER_USERNAME/PASSWORD/EMAIL to enable)."; \
	fi
	$(UV) python src/manage.py runserver 0.0.0.0:8000

clean: ## Clean caches and coverage outputs
	@echo "Cleaning cache and temporary files..."
	rm -rf .mypy_cache/ .pytest_cache/ .venv/ build/ dist/ htmlcov/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t $(DOCKER_IMAGE) .

docker-run: ## Run Docker container (migrate → createsuperuser → start)
	@echo "Running migrations..."
	docker run $(DOCKER_RUN_OPTS) $(DOCKER_IMAGE) migrate
	@if [ -n "$$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$$DJANGO_SUPERUSER_EMAIL" ]; then \
		echo "Ensuring Django superuser exists..."; \
		docker run $(DOCKER_RUN_OPTS) $(DOCKER_IMAGE) createsuperuser --noinput || true; \
	else \
		echo "Skipping createsuperuser (set DJANGO_SUPERUSER_USERNAME/PASSWORD/EMAIL to enable)."; \
	fi
	@echo "Starting server..."
	docker run $(DOCKER_RUN_OPTS) -p 8000:8000 $(DOCKER_IMAGE)

docker: docker-build docker-run ## Build and run Docker container
	@echo "Docker container built and running!"
