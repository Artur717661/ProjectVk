import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PhotoStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed')",
            name="ck_photos_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PhotoStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    faces_count: Mapped[int | None] = mapped_column(Integer)
    eyes_closed_count: Mapped[int | None] = mapped_column(Integer)
    is_blurred: Mapped[bool | None] = mapped_column()
    blur_score: Mapped[float | None] = mapped_column()
    perceptual_hash: Mapped[str | None] = mapped_column(String(255))
    duplicate_group_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
