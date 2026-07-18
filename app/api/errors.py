import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.schemas.photo import ErrorResponse


logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.warning(
            "request_failed",
            extra={
                "event": "request_failed",
                "request_id": request_id,
                "error_code": exc.code,
            },
        )
        body = ErrorResponse(code=exc.code, message=exc.detail, request_id=request_id)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        body = ErrorResponse(
            code="validation_error",
            message="Проверьте данные запроса",
            request_id=request_id,
        )
        return JSONResponse(status_code=422, content=body.model_dump())
