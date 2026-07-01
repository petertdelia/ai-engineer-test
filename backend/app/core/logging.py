import uuid
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Try to extract user_id from the token header without fully verifying
        # (full verification happens in route-level deps — this is best-effort context binding)
        user_id = None
        session_id = None

        # Bind what we know
        if user_id:
            structlog.contextvars.bind_contextvars(user_id=str(user_id))
        if session_id:
            structlog.contextvars.bind_contextvars(session_id=str(session_id))

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def bind_request_context(user_id: str | None = None, session_id: str | None = None) -> None:
    ctx: dict = {}
    if user_id:
        ctx["user_id"] = str(user_id)
    if session_id:
        ctx["session_id"] = str(session_id)
    if ctx:
        structlog.contextvars.bind_contextvars(**ctx)
