import uuid

import pytest

from app.db.models import PhotoStatus
from app.repositories.photo_repository import PhotoRepository

STALE_AFTER = 300


async def _create_photo(repo: PhotoRepository, sha256: str):
    return await repo.create_pending(
        photo_id=uuid.uuid4(),
        object_key="photos/x/original.jpg",
        original_filename="x.jpg",
        content_type="image/jpeg",
        sha256=sha256,
    )


@pytest.mark.asyncio
async def test_atomic_pending_to_processing_transition(db_session):
    repo = PhotoRepository(db_session)
    photo = await _create_photo(repo, "a" * 64)

    first_claim = await repo.try_mark_processing(photo.id, stale_after_seconds=STALE_AFTER)
    second_claim = await repo.try_mark_processing(photo.id, stale_after_seconds=STALE_AFTER)

    assert first_claim is True
    assert second_claim is False


@pytest.mark.asyncio
async def test_claim_increments_attempts(db_session):
    repo = PhotoRepository(db_session)
    photo = await _create_photo(repo, "b" * 64)

    await repo.try_mark_processing(photo.id, stale_after_seconds=STALE_AFTER)

    db_session.expire_all()  # Core UPDATE bypasses the identity map
    claimed = await repo.get_by_id(photo.id)
    assert claimed.status is PhotoStatus.processing
    assert claimed.attempts == 1


@pytest.mark.asyncio
async def test_stale_processing_row_can_be_reclaimed(db_session):
    """A photo abandoned by a dead worker must not stay in `processing` forever."""
    repo = PhotoRepository(db_session)
    photo = await _create_photo(repo, "c" * 64)

    assert await repo.try_mark_processing(photo.id, stale_after_seconds=STALE_AFTER) is True
    # Same row, but now we treat anything older than 0s as abandoned.
    assert await repo.try_mark_processing(photo.id, stale_after_seconds=0) is True

    db_session.expire_all()  # Core UPDATE bypasses the identity map
    reclaimed = await repo.get_by_id(photo.id)
    assert reclaimed.attempts == 2


@pytest.mark.asyncio
async def test_done_photo_is_never_reclaimed(db_session):
    repo = PhotoRepository(db_session)
    photo = await _create_photo(repo, "d" * 64)

    await repo.try_mark_processing(photo.id, stale_after_seconds=STALE_AFTER)
    await repo.mark_done(
        photo.id,
        faces_count=1,
        eyes_closed_count=0,
        is_blurred=False,
        blur_score=12.5,
        perceptual_hash="abc123",
        dominant_color="#336699",
        tags=["test"],
        model_version="v1",
    )

    assert await repo.try_mark_processing(photo.id, stale_after_seconds=0) is False
