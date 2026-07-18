from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session, get_storage
from app.integrations.minio_storage import MinioStorage
from app.schemas.photo import PhotoListResponse, PhotoResponse, UploadPhotoResponse
from app.services.photo_service import PhotoService


router = APIRouter(prefix="/v1/photos", tags=["photos"])


def build_service(session: AsyncSession, storage: MinioStorage) -> PhotoService:
    return PhotoService(session=session, storage=storage)


@router.post("", response_model=UploadPhotoResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    storage: MinioStorage = Depends(get_storage),
) -> UploadPhotoResponse:
    photo = await build_service(session, storage).create_photo(
        file, request.state.request_id
    )
    return UploadPhotoResponse(photo_id=photo.id, status="pending")


@router.get("", response_model=PhotoListResponse)
async def list_photos(
    session: AsyncSession = Depends(get_session),
    storage: MinioStorage = Depends(get_storage),
) -> PhotoListResponse:
    photos = await build_service(session, storage).list_photos()
    return PhotoListResponse(items=[PhotoResponse.model_validate(photo) for photo in photos])


@router.get("/{photo_id}", response_model=PhotoResponse)
async def get_photo(
    photo_id: str,
    session: AsyncSession = Depends(get_session),
    storage: MinioStorage = Depends(get_storage),
) -> PhotoResponse:
    photo = await build_service(session, storage).get_photo(photo_id)
    return PhotoResponse.model_validate(photo)


@router.get("/{photo_id}/content")
async def get_photo_content(
    photo_id: str,
    session: AsyncSession = Depends(get_session),
    storage: MinioStorage = Depends(get_storage),
) -> StreamingResponse:
    photo, content = await build_service(session, storage).get_content(photo_id)

    async def content_stream() -> AsyncGenerator[bytes, None]:
        yield content

    return StreamingResponse(
        content_stream(),
        media_type=photo.content_type,
        headers={"Content-Disposition": f'inline; filename="{photo.filename}"'},
    )
