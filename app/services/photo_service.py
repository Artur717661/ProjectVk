import logging
from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    DependencyUnavailableError,
    FileTooLargeError,
    PhotoNotFoundError,
    UnsupportedFileTypeError,
)
from app.db.models import Photo, PhotoStatus
from app.integrations.minio_storage import MinioStorage
from app.repositories.photo_repository import PhotoRepository


logger = logging.getLogger(__name__)
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class PhotoService:
    def __init__(self, session: AsyncSession, storage: MinioStorage) -> None:
        self.repository = PhotoRepository(session)
        self.storage = storage
        self.settings = get_settings()

    async def create_photo(self, file: UploadFile, request_id: str) -> Photo:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileTypeError()

        content = await file.read(self.settings.max_file_size_bytes + 1)
        if len(content) > self.settings.max_file_size_bytes:
            raise FileTooLargeError()
        if not content:
            raise UnsupportedFileTypeError("Файл пустой или повреждён")

        photo_id = str(uuid4())
        filename = file.filename or "photo"
        extension = PurePosixPath(filename).suffix.lower() or ".bin"
        object_key = f"photos/{photo_id}/original{extension}"
        photo = Photo(
            id=photo_id,
            filename=filename,
            content_type=file.content_type,
            size_bytes=len(content),
            object_key=object_key,
            status=PhotoStatus.PENDING.value,
        )

        await self.storage.put_bytes(object_key, content, file.content_type)
        try:
            photo = await self.repository.create(photo)
        except SQLAlchemyError as exc:
            await self.storage.delete(object_key)
            raise DependencyUnavailableError("PostgreSQL временно недоступен") from exc
        except Exception:
            # Если запись в БД не создалась, не оставляем бесхозный объект.
            await self.storage.delete(object_key)
            raise

        logger.info(
            "photo_created",
            extra={
                "event": "photo_created",
                "request_id": request_id,
                "photo_id": photo.id,
                "status": photo.status,
                "original_filename": photo.filename,
            },
        )
        return photo

    async def list_photos(self) -> list[Photo]:
        try:
            return await self.repository.list()
        except SQLAlchemyError as exc:
            raise DependencyUnavailableError("PostgreSQL временно недоступен") from exc

    async def get_photo(self, photo_id: str) -> Photo:
        try:
            photo = await self.repository.get_by_id(photo_id)
        except SQLAlchemyError as exc:
            raise DependencyUnavailableError("PostgreSQL временно недоступен") from exc
        if photo is None:
            raise PhotoNotFoundError()
        return photo

    async def get_content(self, photo_id: str) -> tuple[Photo, bytes]:
        photo = await self.get_photo(photo_id)
        content = await self.storage.get_bytes(photo.object_key)
        return photo, content
