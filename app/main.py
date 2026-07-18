from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.middleware import RequestIdMiddleware
from app.api.photos import router as photos_router
from app.core.logging import configure_logging


configure_logging()
app = FastAPI(
    title="Photo Analysis Service",
    version="0.1.0",
    description="Загрузка фотографий и подготовка к асинхронному анализу.",
)
app.add_middleware(RequestIdMiddleware)
app.include_router(photos_router)
app.include_router(health_router)
register_exception_handlers(app)
