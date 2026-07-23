import io
import uuid

import pytest
from PIL import Image


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_happy_path(client):
    response = await client.post(
        "/v1/photos", files={"file": ("test.png", _png_bytes(), "image/png")}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert uuid.UUID(body["photo_id"])

    detail = await client.get(f"/v1/photos/{body['photo_id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_same_file_twice_returns_same_photo(client):
    """sha256 dedup: re-uploading identical bytes must not create a second row."""
    png = _png_bytes()

    first = await client.post("/v1/photos", files={"file": ("a.png", png, "image/png")})
    second = await client.post("/v1/photos", files={"file": ("b.png", png, "image/png")})

    assert first.json()["photo_id"] == second.json()["photo_id"]

    listing = await client.get("/v1/photos")
    assert listing.json()["total"] == 1


@pytest.mark.asyncio
async def test_upload_rejects_non_image(client):
    response = await client.post(
        "/v1/photos", files={"file": ("test.txt", b"not an image", "text/plain")}
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


@pytest.mark.asyncio
async def test_upload_rejects_lying_content_type(client):
    """A whitelisted content type with garbage bytes must still be rejected."""
    response = await client.post(
        "/v1/photos", files={"file": ("fake.png", b"definitely not a png", "image/png")}
    )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_svg(client):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

    response = await client.post(
        "/v1/photos", files={"file": ("x.svg", svg, "image/svg+xml")}
    )

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_oversized(client, tiny_upload_limit):
    response = await client.post(
        "/v1/photos", files={"file": ("test.png", _png_bytes(), "image/png")}
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


@pytest.mark.asyncio
async def test_get_photo_not_found(client):
    response = await client.get(f"/v1/photos/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "photo_not_found"


@pytest.mark.asyncio
async def test_photo_content_is_served_back(client):
    png = _png_bytes()
    upload = await client.post("/v1/photos", files={"file": ("p.png", png, "image/png")})

    response = await client.get(f"/v1/photos/{upload.json()['photo_id']}/content")

    assert response.status_code == 200
    assert response.content == png
    assert response.headers["content-type"] == "image/png"
