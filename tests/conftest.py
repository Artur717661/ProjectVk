from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base


class FakeStorageClient:
    """In-memory stand-in for MinIO so API-layer tests don't need a real object store."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def ensure_bucket(self) -> None:
        pass

    async def upload(self, object_key: str, data: bytes, content_type: str) -> None:
        self.objects[object_key] = data

    async def download(self, object_key: str) -> bytes:
        return self.objects[object_key]

    async def health_check(self) -> bool:
        return True


class FakeKafkaProducer:
    """In-memory stand-in for the Kafka producer."""

    def __init__(self) -> None:
        self.published: list[dict] = []
        self._started = True

    @property
    def is_started(self) -> bool:
        return self._started

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def publish_analysis_requested(self, *, photo_id, object_key, trace_id) -> None:
        self.published.append(
            {"photo_id": photo_id, "object_key": object_key, "trace_id": trace_id}
        )


def _test_database_url(app_database_url: str) -> str:
    # Tests run against their own `photo_test` database (created by
    # scripts/init-test-db.sql) instead of the one api/worker use, so a test
    # run can never wipe out data from a live compose stack.
    base, _, _ = app_database_url.rpartition("/")
    return f"{base}/photo_test"


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    # Function-scoped on purpose: each test gets its own event loop, and an engine
    # built on a closed loop fails with "Event loop is closed". create_all is a
    # no-op once the tables exist, so the per-test cost is negligible.
    settings = get_settings()
    engine = create_async_engine(_test_database_url(settings.database_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    session_maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    async with db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE photos, duplicate_groups CASCADE"))


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from app.db.session import get_db
    from app.integrations.kafka_producer import get_kafka_producer
    from app.integrations.storage import get_storage_client
    from app.main import app

    fake_storage = FakeStorageClient()
    fake_kafka = FakeKafkaProducer()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_client] = lambda: fake_storage
    app.dependency_overrides[get_kafka_producer] = lambda: fake_kafka

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def tiny_upload_limit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("MAX_UPLOAD_MB", raising=False)
    get_settings.cache_clear()
