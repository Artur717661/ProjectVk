from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.core.exceptions import DependencyUnavailableError
from app.db.models import Photo


router = APIRouter(tags=["service"])


@router.get("/healthz")
async def healthz(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise DependencyUnavailableError("PostgreSQL временно недоступен") from exc
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise DependencyUnavailableError("PostgreSQL ещё не готов") from exc
    return {"status": "ready"}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(session: AsyncSession = Depends(get_session)) -> PlainTextResponse:
    try:
        photos_total = await session.scalar(select(func.count()).select_from(Photo))
    except SQLAlchemyError as exc:
        raise DependencyUnavailableError("PostgreSQL временно недоступен") from exc
    body = (
        "# HELP photos_total Общее количество загруженных фотографий\n"
        "# TYPE photos_total gauge\n"
        f"photos_total {photos_total or 0}\n"
    )
    return PlainTextResponse(body)
