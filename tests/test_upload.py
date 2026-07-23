import io
import uuid

import pytest
from PIL import Image


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_happy_path(client):
    png = _make_png_bytes()

    response = await client.post(
        "/v1/photos", files={"file": ("test.png", png, "image/png")}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert uuid.UUID(body["photo_id"])

    detail = await client.get(f"/v1/photos/{body['photo_id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_rejects_non_image(client):
    response = await client.post(
        "/v1/photos", files={"file": ("test.txt", b"not an image", "text/plain")}
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


@pytest.mark.asyncio
async def test_upload_rejects_oversized(client, tiny_upload_limit):
    png = _make_png_bytes()

    response = await client.post(
        "/v1/photos", files={"file": ("test.png", png, "image/png")}
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


@pytest.mark.asyncio
async def test_get_photo_not_found(client):
    response = await client.get(f"/v1/photos/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "photo_not_found"
