import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.kafka_producer import KafkaProducerClient, get_kafka_producer
from app.integrations.storage import StorageClient, get_storage_client
from app.schemas.photos import (
    ErrorResponse,
    PhotoDetailResponse,
    PhotoListItem,
    PhotoListResponse,
    PhotoUploadResponse,
)
from app.services.photo_service import PhotoService

router = APIRouter(prefix="/v1/photos", tags=["photos"])


def get_photo_service(
    session: AsyncSession = Depends(get_db),
    storage: StorageClient = Depends(get_storage_client),
    kafka_producer: KafkaProducerClient = Depends(get_kafka_producer),
) -> PhotoService:
    return PhotoService(session, storage, kafka_producer)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PhotoUploadResponse,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    service: PhotoService = Depends(get_photo_service),
) -> PhotoUploadResponse:
    data = await file.read()
    request_id = getattr(request.state, "request_id", "unknown")

    photo = await service.upload_photo(
        filename=file.filename or "unknown",
        content_type=file.content_type,
        data=data,
        request_id=request_id,
    )

    return PhotoUploadResponse(photo_id=photo.id, status=photo.status)


@router.get("", response_model=PhotoListResponse)
async def list_photos(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: PhotoService = Depends(get_photo_service),
) -> PhotoListResponse:
    items, total = await service.list_photos(limit=limit, offset=offset)
    return PhotoListResponse(
        items=[PhotoListItem.model_validate(item) for item in items], total=total
    )


@router.get(
    "/{photo_id}",
    response_model=PhotoDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_photo(
    photo_id: uuid.UUID,
    service: PhotoService = Depends(get_photo_service),
) -> PhotoDetailResponse:
    photo = await service.get_photo(photo_id)
    return PhotoDetailResponse.model_validate(photo)


@router.get(
    "/{photo_id}/content",
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_photo_content(
    photo_id: uuid.UUID,
    service: PhotoService = Depends(get_photo_service),
) -> Response:
    data, content_type = await service.get_photo_content(photo_id)
    return Response(content=data, media_type=content_type)
