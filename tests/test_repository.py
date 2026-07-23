import uuid

import pytest

from app.repositories.photo_repository import PhotoRepository


@pytest.mark.asyncio
async def test_atomic_pending_to_processing_transition(db_session):
    repo = PhotoRepository(db_session)
    photo = await repo.create_pending(
        photo_id=uuid.uuid4(),
        object_key="photos/x/original.jpg",
        original_filename="x.jpg",
        content_type="image/jpeg",
        sha256="a" * 64,
    )

    first_claim = await repo.try_mark_processing(photo.id)
    second_claim = await repo.try_mark_processing(photo.id)

    assert first_claim is True
    assert second_claim is False
