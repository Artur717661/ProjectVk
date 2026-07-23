"""initial schema: photos, duplicate_groups

Revision ID: 0001
Revises:
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "duplicate_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("last_error_message", sa.String(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("faces_count", sa.Integer(), nullable=True),
        sa.Column("eyes_closed_count", sa.Integer(), nullable=True),
        sa.Column("is_blurred", sa.Boolean(), nullable=True),
        sa.Column("blur_score", sa.Float(), nullable=True),
        sa.Column("perceptual_hash", sa.String(), nullable=True),
        sa.Column("dominant_color", sa.String(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column(
            "duplicate_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("duplicate_groups.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed')",
            name="ck_photos_status",
        ),
        sa.UniqueConstraint("sha256", name="uq_photos_sha256"),
    )

    op.create_index("ix_photos_status", "photos", ["status"])
    op.create_index("ix_photos_duplicate_group_id", "photos", ["duplicate_group_id"])
    op.create_index("ix_photos_perceptual_hash", "photos", ["perceptual_hash"])


def downgrade() -> None:
    op.drop_index("ix_photos_perceptual_hash", table_name="photos")
    op.drop_index("ix_photos_duplicate_group_id", table_name="photos")
    op.drop_index("ix_photos_status", table_name="photos")
    op.drop_table("photos")
    op.drop_table("duplicate_groups")
