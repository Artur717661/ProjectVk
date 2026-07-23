import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.photos import router as photos_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.metrics import http_request_duration_seconds, http_requests_total
from app.db.session import engine
from app.integrations.kafka_producer import get_kafka_producer
from app.integrations.storage import get_storage_client

settings = get_settings()
configure_logging(settings.log_level)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = get_storage_client()
    await storage.ensure_bucket()

    kafka_producer = get_kafka_producer()
    await kafka_producer.start()

    logger.info("photo_service_started")
    yield

    await kafka_producer.stop()
    await engine.dispose()
    logger.info("photo_service_stopped")


app = FastAPI(title="Photo Analysis Service", version="0.1.0", lifespan=lifespan)

register_exception_handlers(app)
app.include_router(photos_router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start = time.perf_counter()
    response: Response = await call_next(request)
    duration = time.perf_counter() - start

    path = request.scope.get("route").path if request.scope.get("route") else request.url.path
    http_requests_total.labels(
        method=request.method, path=path, status_code=response.status_code
    ).inc()
    http_request_duration_seconds.labels(method=request.method, path=path).observe(
        duration
    )

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> JSONResponse:
    checks = {"database": False, "storage": False, "kafka": False}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("readyz_database_failed", error=str(exc))

    storage = get_storage_client()
    checks["storage"] = await storage.health_check()

    kafka_producer = get_kafka_producer()
    checks["kafka"] = kafka_producer._started  # noqa: SLF001

    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
