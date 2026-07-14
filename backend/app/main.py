import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError, app_error_handler, generic_exception_handler
from app.core.logging import RequestContextMiddleware, configure_logging

# Configure structured logging
configure_logging()

# Initialize Sentry — skip silently if DSN is absent or a placeholder
if settings.SENTRY_DSN:
    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.1,
            environment="production",
        )
    except Exception:
        pass

app = FastAPI(
    title="Crucible — AI Engineering Assessment Platform",
    description="REST API for the Crucible platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request context logging middleware
app.add_middleware(RequestContextMiddleware)

# Exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Routes
from app.routes import auth, users, sessions, results, topics, admin, public  # noqa: E402

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sessions.router)
app.include_router(results.router)
app.include_router(topics.router)
app.include_router(admin.router)
app.include_router(public.router)
