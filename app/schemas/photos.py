import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import PhotoStatus


class PhotoUploadResponse(BaseModel):
    photo_id: uuid.UUID
    status: PhotoStatus


class PhotoListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    status: PhotoStatus
    created_at: datetime
    updated_at: datetime
    duplicate_group_id: uuid.UUID | None = None


class PhotoDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    status: PhotoStatus
    attempts: int
    last_error_code: str | None = None
    last_error_message: str | None = None

    sha256: str
    faces_count: int | None = None
    eyes_closed_count: int | None = None
    is_blurred: bool | None = None
    blur_score: float | None = None
    perceptual_hash: str | None = None
    dominant_color: str | None = None
    tags: list[str] | None = None
    model_version: str | None = None
    duplicate_group_id: uuid.UUID | None = None

    created_at: datetime
    updated_at: datetime


class PhotoListResponse(BaseModel):
    items: list[PhotoListItem]
    total: int


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str | None = Field(default=None)
