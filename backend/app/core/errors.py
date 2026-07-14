from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        detail: dict | None = None,
        headers: dict | None = None,
    ):
        self.message = message or self.__class__.message
        self.detail = detail or {}
        self.headers = headers or {}
        super().__init__(self.message)


class SessionNotFound(AppError):
    status_code = 404
    error_code = "SESSION_NOT_FOUND"
    message = "Session not found"


class SessionAlreadyCompleted(AppError):
    status_code = 409
    error_code = "SESSION_ALREADY_COMPLETED"
    message = "Session has already been completed"


class SessionNotInProgress(AppError):
    status_code = 409
    error_code = "SESSION_NOT_IN_PROGRESS"
    message = "Session is not in progress"


class SessionExpired(AppError):
    status_code = 409
    error_code = "SESSION_EXPIRED"
    message = "Session time limit has expired"


class UnverifiedEmailRequired(AppError):
    status_code = 403
    error_code = "UNVERIFIED_EMAIL_REQUIRED"
    message = "Email verification required to start Exam sessions"


class InsufficientScoreForCertificate(AppError):
    status_code = 403
    error_code = "INSUFFICIENT_SCORE"
    message = "Score does not meet the minimum threshold for a certificate"


class TurnLimitExceeded(AppError):
    status_code = 429
    error_code = "TURN_LIMIT_EXCEEDED"
    message = "AI assistant turn limit reached for this question"

    def __init__(self, message: str | None = None, detail: dict | None = None):
        super().__init__(message, detail)
        self.detail = {"turn_limit_reached": True}


class RateLimitExceeded(AppError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests, please try again later"


class QuestionNotFound(AppError):
    status_code = 404
    error_code = "QUESTION_NOT_FOUND"
    message = "Question not found"


class UserNotFound(AppError):
    status_code = 404
    error_code = "USER_NOT_FOUND"
    message = "User not found"


class InvalidCredentials(AppError):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    message = "Invalid email or password"


class InvalidToken(AppError):
    status_code = 401
    error_code = "INVALID_TOKEN"
    message = "Invalid or expired token"


class AccountInactive(AppError):
    status_code = 403
    error_code = "ACCOUNT_INACTIVE"
    message = "Account is inactive"


class NotScoredSession(AppError):
    status_code = 409
    error_code = "SESSION_NOT_COMPLETED"
    message = "Session has not been completed"


class InsufficientQuestions(AppError):
    status_code = 422
    error_code = "INSUFFICIENT_QUESTIONS"
    message = "Not enough questions available in the bank to start this session"


class AIAssistantDisabled(AppError):
    status_code = 503
    error_code = "AI_ASSISTANT_DISABLED"
    message = "AI assistant is temporarily unavailable"


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
        },
        headers=exc.headers or None,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import structlog
    import sentry_sdk

    logger = structlog.get_logger()
    logger.error("unhandled_exception", exc_info=exc)
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": {},
        },
    )
