# Crucible — Backend

REST API for the Crucible AI engineering assessment platform.

**Stack:** Python 3.12, FastAPI, PostgreSQL (asyncpg), Redis, Celery, Anthropic SDK

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — `pip install uv`
- PostgreSQL 16
- Redis 7

For local dev, Docker can run Postgres and Redis:

```bash
make up      # starts postgres:5433 and redis:6380 (remapped to avoid conflicts)
make down    # stops them
```

---

## Setup

```bash
cp .env.example .env    # fill in secrets
make install            # uv sync
make migrate            # alembic upgrade head
```

---

## Running

```bash

sudo -u postgres createuser -s "$(whoami)"
createdb crucible
psql -p 5432 -U "$(whoami)" -d postgres -c "ALTER DATABASE crucible OWNER TO crucible;" 2>&1

make migrate
make run        # FastAPI dev server — http://localhost:8000
make worker     # Celery worker (separate terminal)
```

Swagger UI: `http://localhost:8000/docs`

---

## Environment Variables

Key variables — see `.env.example` for the full list:

| Variable | Description |
|---|---|
| `DATABASE_URL` | asyncpg connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key (generate with `openssl rand -hex 32`) |
| `ANTHROPIC_API_KEY` | Claude API key |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth credentials |
| `RESEND_API_KEY` | Transactional email |
| `S3_BUCKET_NAME` / `AWS_*` | Certificate image storage |
| `SENTRY_DSN` | Optional error tracking |

---

## Testing

Unit and API tests run without Docker against an in-memory SQLite database:

```bash
make test               # full suite
make test-unit          # unit tests only (no database needed)
make test-api           # API integration tests
```

Repository and worker tests require a real PostgreSQL instance:

```bash
# Using an existing local Postgres:
sudo -u postgres createuser -s "$(whoami)"
createdb crucible_test
psql -p 5432 -U "$(whoami)" -d postgres -c "CREATE ROLE crucible WITH LOGIN PASSWORD 'crucible';" 2>&1
psql -p 5432 -U "$(whoami)" -d postgres -c "ALTER DATABASE crucible_test OWNER TO crucible;" 2>&1
psql -h localhost -p 5432 -U crucible -d crucible_test -c "select current_user, current_database();" <<< "crucible" 2>&1


DATABASE_URL=postgresql+asyncpg://crucible:crucible@localhost:5432/crucible_test \
REDIS_URL=redis://localhost:6379/0 \
uv run pytest tests/repository/ tests/workers/

# Or spin up the CI compose (uses ports 5434/6381 to avoid conflicts):
docker compose -f docker-compose.ci.yml up -d
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/test \
REDIS_URL=redis://localhost:6381/0 \
uv run pytest
docker compose -f docker-compose.ci.yml down
```

---

## Project Structure

```
app/
  core/         config, auth, AI client, scoring engine, email, certificates
  models/       SQLAlchemy ORM definitions
  repository/   all SQL — no HTTP concepts
  routes/       HTTP only — parse request, call repository, return response
  schemas/      Pydantic request/response models
  workers/      Celery tasks (scoring, pipeline, cleanup) and Beat schedule
alembic/        database migrations
tests/
  unit/         pure logic — no I/O
  api/          HTTP integration tests (httpx + SQLite)
  repository/   SQL correctness tests (real Postgres)
  workers/      Celery tasks in eager mode
```

---

## Architecture Conventions

- **Routes call repositories, not models directly.** No SQL in route handlers.
- **Repositories return ORM objects or `None`, never raise HTTP errors.**
- **All domain errors are typed exceptions** defined in `core/errors.py`.
- **Never call Claude from a route handler** — all AI calls go through `core/ai.py` or a Celery worker.
- **All thresholds and timeouts are constants** in `core/config.py`.

---

## Deployment

Deployed to Heroku as a separate app from the frontend. The `Procfile` defines three process types:

```
web:     uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
worker:  celery -A app.workers.celery_app worker
beat:    celery -A app.workers.celery_app beat
release: alembic upgrade head
```

Set `DATABASE_URL` and `REDIS_URL` via Heroku config vars — the app detects `postgres://` scheme and rewrites it to `postgresql+asyncpg://` automatically.
