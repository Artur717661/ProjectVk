import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DuplicatePhotoError
from app.db.models import DuplicateGroup, Photo, PhotoStatus


class PhotoRepository:
    """All SQL for the photos/duplicate_groups tables lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_pending(
        self,
        *,
        photo_id: uuid.UUID,
        object_key: str,
        original_filename: str,
        content_type: str,
        sha256: str,
    ) -> Photo:
        photo = Photo(
            id=photo_id,
            object_key=object_key,
            original_filename=original_filename,
            content_type=content_type,
            sha256=sha256,
            status=PhotoStatus.pending,
        )
        self.session.add(photo)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicatePhotoError(
                f"Photo with sha256={sha256} already exists"
            ) from exc
        await self.session.refresh(photo)
        return photo

    async def get_by_id(self, photo_id: uuid.UUID) -> Photo | None:
        return await self.session.get(Photo, photo_id)

    async def get_by_sha256(self, sha256: str) -> Photo | None:
        stmt = select(Photo).where(Photo.sha256 == sha256)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_photos(self, *, limit: int, offset: int) -> tuple[list[Photo], int]:
        items_stmt = (
            select(Photo).order_by(Photo.created_at.desc()).limit(limit).offset(offset)
        )
        count_stmt = select(func.count()).select_from(Photo)

        items_result = await self.session.execute(items_stmt)
        count_result = await self.session.execute(count_stmt)

        return list(items_result.scalars().all()), count_result.scalar_one()

    async def try_mark_processing(self, photo_id: uuid.UUID) -> bool:
        """Atomic pending->processing transition; False means already claimed."""
        stmt = (
            update(Photo)
            .where(Photo.id == photo_id, Photo.status == PhotoStatus.pending)
            .values(status=PhotoStatus.processing, attempts=Photo.attempts + 1)
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def mark_done(
        self,
        photo_id: uuid.UUID,
        *,
        faces_count: int,
        eyes_closed_count: int,
        is_blurred: bool,
        blur_score: float,
        perceptual_hash: str,
        dominant_color: str,
        tags: list[str],
        model_version: str,
    ) -> None:
        stmt = (
            update(Photo)
            .where(Photo.id == photo_id)
            .values(
                status=PhotoStatus.done,
                faces_count=faces_count,
                eyes_closed_count=eyes_closed_count,
                is_blurred=is_blurred,
                blur_score=blur_score,
                perceptual_hash=perceptual_hash,
                dominant_color=dominant_color,
                tags=tags,
                model_version=model_version,
                last_error_code=None,
                last_error_message=None,
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def mark_failed(
        self, photo_id: uuid.UUID, *, error_code: str, error_message: str
    ) -> None:
        stmt = (
            update(Photo)
            .where(Photo.id == photo_id)
            .values(
                status=PhotoStatus.failed,
                last_error_code=error_code,
                last_error_message=error_message,
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_hash_candidates(
        self, exclude_photo_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, str, uuid.UUID | None]]:
        """Other photos' hashes, for in-process hamming-distance comparison."""
        stmt = select(Photo.id, Photo.perceptual_hash, Photo.duplicate_group_id).where(
            Photo.perceptual_hash.is_not(None),
            Photo.id != exclude_photo_id,
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def create_duplicate_group(self) -> DuplicateGroup:
        group = DuplicateGroup()
        self.session.add(group)
        await self.session.flush()
        return group

    async def assign_duplicate_group(
        self, photo_ids: list[uuid.UUID], group_id: uuid.UUID
    ) -> None:
        stmt = (
            update(Photo)
            .where(Photo.id.in_(photo_ids))
            .values(duplicate_group_id=group_id)
        )
        await self.session.execute(stmt)
        await self.session.commit()
