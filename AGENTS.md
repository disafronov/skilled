# AGENTS.md

## Documentation Convention

- **Docstrings**: required on all model classes, QuerySet methods, public functions, and modules.
- **HOW comments**: required when the code takes a non-obvious approach:
  - Process supervision in `apps/ops/management/supervisor.py` — document signal forwarding and forced shutdown behavior.
  - Legacy schedule cleanup migration — explain that the external package recreates current schedules via `post_migrate`.

## Commands

```sh
make install          # deps + pre-commit hooks
make format           # black + isort
make lint             # black --check, isort --check-only, flake8, mypy, bandit
make test             # pytest with coverage (100% fail_under)
make dead-code        # vulture
make all              # lint → test → dead-code
make run              # migrate + createsuperuser + dev server (qcluster + runserver)
make q2               # qcluster only
make makemigrations   # DJANGO_SECRET_KEY already set
make migrate          # DJANGO_SECRET_KEY already set
make docker-build     # build production image
make docker-run       # migrate + createsuperuser + run production image
```

**Never** run `manage.py test` — it's intentionally blocked. Use `make test` or `uv run pytest`.

Run a single test: `uv run pytest path/to/test_file.py::test_name -v`
DJANGO_SECRET_KEY is required for any Django command; `make` wrappers set it automatically.

## Lint & Type Check

- **black** (line-length=88), **isort** (profile=black), **flake8** (max-line-length=88, ignores E203/W503)
- **mypy**: strict mode (disallow_untyped_defs, disallow_incomplete_defs, disallow_untyped_decorators, strict_equality). Uses django-stubs plugin. Excludes: tests/, migrations/, manage.py. django-q2 stubs ignored via ignore_missing_imports.
- **bandit**: security lint
- **vulture**: dead code detection

Order: `lint` → `test` → `dead-code`

## Test Quirks

- Settings module: `config.settings_pytest` (disables WhiteNoise + SSL redirects)
- Coverage: 100% branch coverage required (`fail_under=100`, `branch=true`, `parallel=true`)
- Parallel: `-n auto` (pytest-xdist)

## Architecture

Telegram → Job Queue (django-q2) → LLM Worker → Telegram delivery

- `apps/ops/q2.py` — django-q2 scheduled task functions (cleanup_q2_successes)
- `apps/ops/health.py` — `/health/liveness/`, `/health/readiness/` (Docker HEALTHCHECK)
- `apps/ops/apps.py` — Q2 schedule management for cleanup task
- `django-telegram-q2` — external Bot, Job, IntakeBuffer models; pipeline tasks, webhook view, admin, signals, Q2 schedule management, abstract Worker, and Telegram Bot API client
- `apps/library` — Skill & Wrapper models (prompt content)
- `apps/inference` — Provider, Profile & Worker models; LLM client; task orchestrator
- `config/` — Django settings, urls, wsgi

## Gotchas

- **DJANGO_SECRET_KEY**: Must be set for any `manage.py` command. Makefile uses `unsafe-secret-key-for-tooling`.
- **Q2 schedules** are managed by stable name in `django-telegram-q2` and `apps/ops/apps.py` — admin edits are overwritten on save via `pre_save` signal.
- **Engine upgrade**: `apps/ops/migrations/0001_remove_legacy_engine_schedules.py` deletes obsolete `engine.*` schedules; `post_migrate` recreates the package-owned schedules.
- **Git dependency**: `django-telegram-q2` is resolved from Git and pinned by `uv.lock`; Docker installs Git in the builder stage only.
- **Delivery retries**: scheduled `telegram_deliver` drains jobs that have not started delivery; it intentionally does not reset stale `delivery_started_at` jobs because an error after Telegram accepts a message would make an automatic resend duplicate the reply.
- **`policy.md`** is gitignored, loaded at runtime via `POLICY_FILE` env var.
- **Pre-commit**: runs `make lint` + `uv lock` on commit; `make test` + `make dead-code` + `make audit` on push.
- **Conventional commits** enforced via `conventional-pre-commit` hook on commit messages.
- **Semantic release**: `release` branch → stable, `main` → rc prereleases. Release commits auto-rebase open PRs.
- **Docker**: production uses `manage.py start` (qcluster + gunicorn); dev uses `manage.py dev` (qcluster + runserver).
