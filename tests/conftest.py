import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.sqlite3"

from app.core.dependencies import get_session, get_storage  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402


class FakeStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def put_bytes(self, object_key: str, content: bytes, content_type: str) -> None:
        self.files[object_key] = content

    async def get_bytes(self, object_key: str) -> bytes:
        return self.files[object_key]

    async def delete(self, object_key: str) -> None:
        self.files.pop(object_key, None)


engine = create_async_engine("sqlite+aiosqlite:///./test.sqlite3")
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
storage = FakeStorage()


async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


def override_get_storage() -> FakeStorage:
    return storage


app.dependency_overrides[get_session] = override_get_session
app.dependency_overrides[get_storage] = override_get_storage


@pytest_asyncio.fixture(autouse=True)
async def prepare_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    storage.files.clear()
    yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client


async def teardown_database() -> None:
    await engine.dispose()
