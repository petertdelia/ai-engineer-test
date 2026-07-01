# Convenience targets — delegate to backend/ and frontend/ sub-makes.
# Run backend targets directly: cd backend && make <target>
# Run frontend: cd frontend && npm run <script>

.PHONY: up down install migrate run worker test frontend-dev frontend-build

up:
	cd backend && docker compose up -d

down:
	cd backend && docker compose down

install:
	cd backend && uv sync
	cd frontend && npm install

migrate:
	cd backend && uv run alembic upgrade head

run:
	cd backend && uv run uvicorn app.main:app --reload

worker:
	cd backend && uv run celery -A app.workers.celery_app worker --loglevel=info

test:
	cd backend && uv run pytest

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
