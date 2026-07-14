up:
	docker compose up -d

install:
	uv sync

migrate:
	uv run alembic upgrade head

run:
	uv run uvicorn app.main:app --reload

worker:
	uv run celery -A app.workers.celery_app worker --loglevel=info

test:
	DATABASE_URL=postgresql+asyncpg://crucible:crucible@localhost:5432/crucible_test \
	REDIS_URL=redis://localhost:6379/0 \
	uv run pytest

test-unit:
	uv run pytest tests/unit/ -v

test-repo:
	uv run pytest tests/repository/ -v

test-api:
	uv run pytest tests/api/ -v

test-worker:
	uv run pytest tests/workers/ -v

down:
	docker compose down
