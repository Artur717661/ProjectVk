from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import PhotoStatus


class UploadPhotoResponse(BaseModel):
    photo_id: str
    status: Literal["pending"]


class PhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: PhotoStatus
    faces_count: int | None = None
    eyes_closed_count: int | None = None
    is_blurred: bool | None = None
    blur_score: float | None = None
    perceptual_hash: str | None = None
    duplicate_group_id: str | None = None
    created_at: datetime


class PhotoListResponse(BaseModel):
    items: list[PhotoResponse] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
