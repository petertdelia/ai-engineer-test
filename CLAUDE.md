# AI Engineer Platform — Backend

REST API for an AI-era engineering assessment platform. Python, FastAPI, PostgreSQL, Redis, Celery. See [plan-backend.md](plan-backend.md) for the full design.

---

## Setup

```bash
make up        # start PostgreSQL + Redis via docker-compose
make install   # install dependencies via uv
make migrate   # apply Alembic migrations
make run       # start FastAPI dev server at http://localhost:8000
make worker    # start Celery worker + Beat (separate terminal)
make test      # run test suite
make down      # stop Docker containers
```

Swagger UI: `http://localhost:8000/docs`

Copy `.env.example` to `.env` before first run.

---

## Architecture

Four layers — keep them strictly separated:

```
routes/      — HTTP only: parse request, call repository or core, shape response, set status code
repository/  — All SQL lives here. No business logic. No HTTP concepts.
models/      — SQLAlchemy ORM definitions only. No methods, no logic.
schemas/     — Pydantic models for request validation and response serialization.
```

Supporting modules in `core/`:
- `auth.py` — JWT creation/verification, password hashing, Google OAuth token verification
- `ai.py` — Anthropic SDK client, system prompt enforcement, `pybreaker` instance
- `scoring.py` — Scoring engine: calls Claude per dimension, writes scores and rationale
- `email.py` — Sends transactional email via Resend; renders templates
- `errors.py` — Custom exception classes and FastAPI exception handlers
- `logging.py` — `structlog` config, request_id middleware
- `config.py` — `pydantic-settings` typed config; all constants live here (`CERTIFICATE_MIN_SCORE`, `LEADERBOARD_MIN_POPULATION`, inactivity timeouts per mode)
- `certificates.py` — Pillow image rendering, S3 upload

Background workers in `workers/`:
- `scoring.py` — Celery task: scores a completed session, updates `SessionScore`
- `pipeline.py` — Celery task: runs the AI question generation pipeline
- `cleanup.py` — Celery task: marks stale sessions abandoned, purges expired accounts
- `beat.py` — Celery Beat schedule definitions

---

## Key Conventions

**Routes call repositories, not models directly.** The route layer never imports `Session` or runs queries — it calls a repository function and gets back a schema or raises a domain exception.

**Repositories return ORM objects or None, never raise HTTP errors.** HTTP status codes belong in routes. A repository function returns `None` for not-found; the route converts that to `404`.

**All domain errors are typed exceptions.** Define them in `core/errors.py` and register handlers in `main.py`. Never `raise HTTPException` inline in a route — use a typed exception like `SessionNotFound` or `UnverifiedEmailRequired`. This keeps routes readable and error behavior testable.

**Never call Claude from a route handler.** All Claude calls go through `core/ai.py` or happen inside a Celery worker. Routes are thin.

**Config over magic.** Every threshold, limit, and timeout is a named constant in `core/config.py`. Never hardcode numbers inline.

**structlog context binding.** At the start of every request, bind `request_id`, `user_id` (if authed), and `session_id` (if present) to the structlog context. All log calls downstream will automatically include these without passing them explicitly.

---

## Environment Variables

Key variables (see `.env.example` for the full list):

```
DATABASE_URL          postgresql+asyncpg://user:pass@localhost:5432/ai_engineer
REDIS_URL             redis://localhost:6379/0
SECRET_KEY            <random 32-byte hex>
ANTHROPIC_API_KEY     <your key>
RESEND_API_KEY        <your key>
S3_BUCKET             <bucket name>
AWS_ACCESS_KEY_ID     <key>
AWS_SECRET_ACCESS_KEY <secret>
SENTRY_DSN            <optional>
GOOGLE_CLIENT_ID      <OAuth client id>
```

---

## Testing Strategy

### Philosophy

- **Test behavior, not implementation.** Assert on HTTP responses and database state, not on which internal functions were called.
- **Real database for integration tests.** Never mock the database — a mock that passes while the real query fails is worse than no test. Integration tests run against a real PostgreSQL instance (via docker-compose in CI).
- **Mock at external boundaries only.** Mock Claude, S3, Resend, and Google OAuth — everything else runs for real.
- **Unit tests for pure logic.** Scoring calculations, question selection algorithm, JWT helpers, and certificate rendering are tested in isolation without any I/O.

### Test Layers

#### Unit Tests — `tests/unit/`

No database, no HTTP, no external services. Pure Python logic.

- `test_scoring_logic.py` — scoring rubric calculations, difficulty modifier application, dimension weight formulas
- `test_question_selection.py` — selection algorithm: balance constraints, deduplication, fallback logic; drive with in-memory lists of fake questions
- `test_auth_tokens.py` — JWT creation and verification, token expiry, password hash/verify helpers, email-verification token invalidation on password change
- `test_certificate_rendering.py` — Pillow rendering with a fixture image; assert pixel dimensions and that key text appears in the output (no S3 call)

#### Repository Tests — `tests/repository/`

Hit a real PostgreSQL database. Test SQL correctness, constraint enforcement, and query results. No HTTP layer involved.

```python
# conftest.py provides:
# - async_engine: bound to a test schema, rolled back after each test
# - db_session: AsyncSession within the test transaction
```

- `test_users_repo.py` — create, get by email, update, anonymize-on-delete
- `test_questions_repo.py` — filter by category/difficulty/vetted, `technologies` JSONB array queries
- `test_sessions_repo.py` — session state transitions, question selection query, autosave upsert
- `test_scores_repo.py` — pending/completed/failed transitions, `failure_reason` writes
- `test_stats_repo.py` — the `jsonb_array_elements_text` unnesting query that powers `GET /users/me/stats`; assert per-technology breakdowns against known fixture data

Each repository test wraps its work in a transaction that rolls back at teardown — tests are fully isolated and leave no state behind.

#### API (Integration) Tests — `tests/api/`

Use `httpx.AsyncClient` against the live FastAPI app. These are the primary correctness tests.

```python
# conftest.py provides:
# - client: AsyncClient with the test app
# - authed_client: client with a valid JWT cookie for a test user
# - admin_client: client with is_admin=True
# - mock_claude: pytest fixture that patches core/ai.py to return canned responses
# - mock_s3: patches boto3 calls
# - mock_email: patches core/email.py send functions
```

Key test files:

- `test_auth.py` — register, login, Google OAuth, email verification flow, password reset, rate limit enforcement (assert 429 on 4th attempt)
- `test_sessions.py` — create, start (verify question selection ran), respond, autosave, complete, abandon, integrity events; assert that `POST /respond` is rejected after time limit
- `test_ai_chat.py` — message accepted, 429 on turn 16, response suppressed when classifier flags a direct answer, circuit breaker state reflected in session
- `test_results.py` — poll while pending, render when completed, correct 409 before session complete, failed state returned with failure_reason
- `test_admin.py` — vet a question, trigger pipeline (verify `PipelineRun` record created), rescore a failed session, GDPR user delete via admin endpoint
- `test_leaderboard.py` — no data below population threshold, correct filtering on `is_public_rank`

#### Worker Tests — `tests/workers/`

Test Celery tasks in "eager" mode (`CELERY_TASK_ALWAYS_EAGER=True`) so tasks run synchronously in the test process.

- `test_scoring_worker.py` — mock Claude call returning canned scores, assert `SessionScore.status` transitions to `"completed"`, assert score columns written correctly; mock Claude raising an error 3× and assert `status="failed"` and `failure_reason` populated
- `test_pipeline_worker.py` — mock Claude generate + quality-check calls, assert `PipelineRun` record counts are correct, assert questions enter vet queue
- `test_cleanup_worker.py` — seed stale sessions and expired accounts; run cleanup; assert correct records updated/deleted

### Mocking External Services

**Claude (`core/ai.py`):**
```python
@pytest.fixture
def mock_claude(monkeypatch):
    async def fake_message(*args, **kwargs):
        return FakeAnthropicResponse(content="Mocked Claude response")
    monkeypatch.setattr("core.ai.client.messages.create", fake_message)
```
For scoring tests, the fixture returns a structured JSON response matching the `{"score": int, "rationale": str}` shape.

**S3 (`boto3`):**
```python
@pytest.fixture
def mock_s3(monkeypatch):
    monkeypatch.setattr("core.certificates.s3_client.upload_fileobj", AsyncMock())
```

**Resend (`core/email.py`):**
```python
@pytest.fixture(autouse=True)
def mock_email(monkeypatch):
    monkeypatch.setattr("core.email.send", AsyncMock())
```
Marked `autouse=True` so no test accidentally sends real email.

**Google OAuth:** Patch the token verification call to return a canned `{"sub": "google-uid", "email": "test@example.com"}` payload.

### Test Database Setup

`conftest.py` at the root creates a dedicated `test` database schema on startup. Each test function gets a fresh transaction via `AsyncSession` that rolls back on teardown. The schema is created once per session via `async_engine.begin(); Base.metadata.create_all()` and dropped at the end.

For CI, `docker-compose.ci.yml` spins up PostgreSQL and Redis. Tests run with `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/test`.

### Running Tests

```bash
make test                         # full suite
uv run pytest tests/unit/         # unit tests only (no Docker required)
uv run pytest tests/api/ -v       # API tests with verbose output
uv run pytest -k "test_scoring"   # run any test matching "scoring"
uv run pytest --cov=app --cov-report=term-missing  # with coverage
```

### Coverage Targets

| Layer | Target |
|---|---|
| `core/` | 90%+ |
| `repository/` | 95%+ |
| `routes/` | 85%+ |
| `workers/` | 80%+ |

The scoring engine, question selection algorithm, and auth token logic are the highest-value coverage targets — bugs there affect every candidate. The certificate rendering and S3 upload path can have lower coverage since they're exercised by a single integration test.

### What Not to Test

- SQLAlchemy internals — trust the ORM
- Pydantic validation — test that your schemas accept valid input and reject invalid; don't test that Pydantic itself validates types
- Alembic migrations — run them in CI, don't unit-test the migration files
- Third-party SDK behavior (Anthropic, boto3, Resend) — that's their test suite's job; mock at your boundary

---

## Common Tasks

**Add a new route:**
1. Add the function to the appropriate `routes/` file
2. Add any new SQL to the corresponding `repository/` file
3. Add request/response schemas to `schemas/`
4. Register the router in `main.py` if it's a new file
5. Write an API test in `tests/api/`

**Add a database column:**
1. Add the field to the model in `models/`
2. Generate the migration: `uv run alembic revision --autogenerate -m "add <column> to <table>"`
3. Review the generated file in `alembic/versions/` — verify `upgrade()` and `downgrade()`; autogenerate misses renames (drop+add instead)
4. Apply: `make migrate`

**Add a Celery task:**
1. Define the task in the appropriate `workers/` file
2. If it's periodic, add it to `workers/beat.py`
3. Write a worker test using `CELERY_TASK_ALWAYS_EAGER=True`

**Change a scoring threshold or timeout:**
All constants live in `core/config.py`. Do not hardcode values elsewhere.
