import hashlib
import io
import uuid

import structlog
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    DuplicatePhotoError,
    PayloadTooLargeError,
    PhotoNotFoundError,
    UnsupportedMediaTypeError,
)
from app.core.metrics import photos_uploaded_total
from app.db.models import Photo
from app.integrations.kafka_producer import KafkaProducerClient
from app.integrations.storage import StorageClient
from app.repositories.photo_repository import PhotoRepository

logger = structlog.get_logger(__name__)

# Raster formats only, and only ones Pillow can actually decode. Anything outside
# this map is rejected — that also keeps SVG (which can carry scripts) out of the
# bucket, since we serve stored bytes back under their own content type.
_EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/tiff": "tiff",
}


def _normalize_content_type(content_type: str | None) -> str:
    """`image/jpeg; charset=binary` -> `image/jpeg`."""
    return (content_type or "").split(";", 1)[0].strip().lower()


class PhotoService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageClient,
        kafka_producer: KafkaProducerClient,
    ) -> None:
        self._repo = PhotoRepository(session)
        self._storage = storage
        self._kafka = kafka_producer

    async def upload_photo(
        self,
        *,
        filename: str,
        content_type: str | None,
        data: bytes,
        request_id: str,
    ) -> Photo:
        settings = get_settings()

        max_bytes = settings.max_upload_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise PayloadTooLargeError(
                f"File exceeds the {settings.max_upload_mb}MB limit"
            )

        media_type = _normalize_content_type(content_type)
        if media_type not in _EXTENSION_BY_CONTENT_TYPE:
            raise UnsupportedMediaTypeError(
                f"Unsupported content type: {content_type}"
            )

        # Trust the bytes, not the header: Pillow has to actually recognise the
        # image. Any decode failure (including decompression bombs) means the
        # upload is not a usable image, so it maps to 415 rather than a 500.
        try:
            Image.open(io.BytesIO(data)).verify()
        except Exception as exc:  # noqa: BLE001 - any decode failure is a bad upload
            raise UnsupportedMediaTypeError(f"File is not a valid image: {exc}") from exc

        sha256 = hashlib.sha256(data).hexdigest()

        existing = await self._repo.get_by_sha256(sha256)
        if existing is not None:
            logger.info(
                "duplicate_upload_by_sha256",
                photo_id=str(existing.id),
                request_id=request_id,
            )
            return existing

        photo_id = uuid.uuid4()
        object_key = f"photos/{photo_id}/original.{_EXTENSION_BY_CONTENT_TYPE[media_type]}"

        await self._storage.upload(object_key, data, media_type)

        try:
            photo = await self._repo.create_pending(
                photo_id=photo_id,
                object_key=object_key,
                original_filename=filename,
                content_type=media_type,
                sha256=sha256,
            )
        except DuplicatePhotoError:
            # Race: another request inserted the same sha256 first.
            existing = await self._repo.get_by_sha256(sha256)
            if existing is not None:
                return existing
            raise

        try:
            await self._kafka.publish_analysis_requested(
                photo_id=photo.id, object_key=object_key, trace_id=request_id
            )
        except Exception:
            await self._repo.mark_failed(
                photo.id,
                error_code="kafka_publish_failed",
                error_message="Failed to publish analysis request",
            )
            raise

        photos_uploaded_total.inc()
        logger.info("photo_uploaded", photo_id=str(photo.id), request_id=request_id)
        return photo

    async def get_photo(self, photo_id: uuid.UUID) -> Photo:
        photo = await self._repo.get_by_id(photo_id)
        if photo is None:
            raise PhotoNotFoundError(f"Photo {photo_id} not found")
        return photo

    async def list_photos(self, *, limit: int, offset: int) -> tuple[list[Photo], int]:
        return await self._repo.list_photos(limit=limit, offset=offset)

    async def get_photo_content(self, photo_id: uuid.UUID) -> tuple[bytes, str]:
        photo = await self.get_photo(photo_id)
        data = await self._storage.download(photo.object_key)
        return data, photo.content_type
