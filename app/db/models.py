import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PhotoStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    photos: Mapped[list["Photo"]] = relationship(back_populates="duplicate_group")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    object_key: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)

    # native_enum=False keeps this a VARCHAR guarded by a CHECK constraint, so the
    # column matches the migration exactly and new statuses don't need an ALTER TYPE.
    status: Mapped[PhotoStatus] = mapped_column(
        Enum(
            PhotoStatus,
            name="ck_photos_status",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=PhotoStatus.pending,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    faces_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eyes_closed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_blurred: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    perceptual_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    dominant_color: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)

    duplicate_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("duplicate_groups.id"),
        nullable=True,
        index=True,
    )
    duplicate_group: Mapped[DuplicateGroup | None] = relationship(
        back_populates="photos"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
