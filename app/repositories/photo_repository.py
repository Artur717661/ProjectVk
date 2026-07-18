from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Photo, PhotoStatus


class PhotoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, photo: Photo) -> Photo:
        self.session.add(photo)
        await self.session.commit()
        await self.session.refresh(photo)
        return photo

    async def get_by_id(self, photo_id: str) -> Photo | None:
        return await self.session.get(Photo, photo_id)

    async def list(self) -> list[Photo]:
        result = await self.session.scalars(select(Photo).order_by(Photo.created_at.desc()))
        return list(result)

    async def update_status(
        self,
        photo_id: str,
        status: PhotoStatus,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        photo = await self.get_by_id(photo_id)
        if photo is None:
            return
        photo.status = status.value
        photo.last_error_code = error_code
        photo.last_error_message = error_message
        await self.session.commit()
