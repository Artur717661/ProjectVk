from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.integrations.minio_storage import MinioStorage


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def get_storage(request: Request) -> MinioStorage:
    # Один клиент MinIO на приложение проще, чем создавать его для каждого запроса.
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        storage = MinioStorage()
        request.app.state.storage = storage
    return storage
