import io

import structlog
from miniopy_async import Minio

from app.core.config import get_settings
from app.core.errors import StorageUnavailableError
from app.core.metrics import storage_upload_errors_total

logger = structlog.get_logger(__name__)


class StorageClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.minio_bucket
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    async def ensure_bucket(self) -> None:
        try:
            exists = await self._client.bucket_exists(self._bucket)
            if not exists:
                await self._client.make_bucket(self._bucket)
                logger.info("minio_bucket_created", bucket=self._bucket)
        except Exception as exc:  # noqa: BLE001 - any client/network error
            raise StorageUnavailableError(f"Cannot reach MinIO: {exc}") from exc

    async def upload(self, object_key: str, data: bytes, content_type: str) -> None:
        try:
            stream = io.BytesIO(data)
            await self._client.put_object(
                self._bucket,
                object_key,
                stream,
                length=len(data),
                content_type=content_type,
            )
        except Exception as exc:  # noqa: BLE001
            storage_upload_errors_total.inc()
            logger.error("minio_upload_failed", object_key=object_key, error=str(exc))
            raise StorageUnavailableError(f"Failed to upload to MinIO: {exc}") from exc

    async def download(self, object_key: str) -> bytes:
        response = None
        try:
            response = await self._client.get_object(self._bucket, object_key)
            return await response.read()
        except Exception as exc:  # noqa: BLE001
            logger.error("minio_download_failed", object_key=object_key, error=str(exc))
            raise StorageUnavailableError(
                f"Failed to download from MinIO: {exc}"
            ) from exc
        finally:
            if response is not None:
                close = getattr(response, "release_conn", None) or getattr(
                    response, "close", None
                )
                if close is not None:
                    try:
                        close()
                    except Exception:  # noqa: BLE001
                        pass

    async def health_check(self) -> bool:
        try:
            await self._client.bucket_exists(self._bucket)
            return True
        except Exception:  # noqa: BLE001
            return False


_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
