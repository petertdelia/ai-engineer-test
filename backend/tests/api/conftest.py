"""
API test conftest — re-exports shared fixtures from root conftest.
All API tests use the SQLite-backed client fixture.
"""
# Re-export helpers so api/ tests can import from tests.conftest
from tests.conftest import create_test_user, auth_headers, _make_redis_mock  # noqa: F401
