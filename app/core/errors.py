from __future__ import annotations

import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """Base class for domain errors that map 1:1 to an HTTP response."""

    code: str = "internal_error"
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.code
        super().__init__(self.message)


class UnsupportedMediaTypeError(AppError):
    code = "unsupported_media_type"
    http_status = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


class PayloadTooLargeError(AppError):
    code = "payload_too_large"
    http_status = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class PhotoNotFoundError(AppError):
    code = "photo_not_found"
    http_status = status.HTTP_404_NOT_FOUND


class StorageUnavailableError(AppError):
    code = "storage_unavailable"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE


class KafkaUnavailableError(AppError):
    code = "kafka_unavailable"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE


class DuplicatePhotoError(AppError):
    code = "duplicate_photo"
    http_status = status.HTTP_409_CONFLICT


# --- gRPC analyzer errors, used by analyzer_client.py and the worker (not exposed over HTTP)


class AnalyzerError(Exception):
    code: str = "analyzer_error"
    retryable: bool = False

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AnalyzerTransientError(AnalyzerError):
    """UNAVAILABLE / DEADLINE_EXCEEDED / RESOURCE_EXHAUSTED / INTERNAL after retries exhausted."""

    code = "analyzer_unavailable"
    retryable = True


class AnalyzerInvalidArgumentError(AnalyzerError):
    """Bad request payload - never retried."""

    code = "analyzer_invalid_argument"
    retryable = False


class AnalyzerUnknownError(AnalyzerError):
    code = "analyzer_unknown_error"
    retryable = False


def _error_body(request: Request, code: str, message: str) -> dict:
    request_id = getattr(request.state, "request_id", None)
    return {
        "error": {
            "code": code,
            "message": message,
        },
        "request_id": request_id,
    }


def register_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_error",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(request, exc.code, exc.message),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_error",
            error=str(exc),
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(request, "internal_error", "Internal server error"),
        )
