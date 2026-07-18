from uuid import uuid4

from httpx import AsyncClient


async def test_upload_get_list_and_content(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/photos",
        files={"file": ("cat.jpg", b"fake-image", "image/jpeg")},
        headers={"X-Request-ID": "test-request-1"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "pending"
    photo_id = payload["photo_id"]
    assert response.headers["X-Request-ID"] == "test-request-1"

    item = await client.get(f"/v1/photos/{photo_id}")
    assert item.status_code == 200
    assert item.json()["filename"] == "cat.jpg"
    assert item.json()["status"] == "pending"

    listing = await client.get("/v1/photos")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1

    content = await client.get(f"/v1/photos/{photo_id}/content")
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/jpeg"
    assert content.content == b"fake-image"


async def test_unsupported_file_type_returns_415(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/photos",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_file_type"
    assert response.json()["request_id"]


async def test_unknown_photo_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/v1/photos/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "photo_not_found"


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_and_metrics(client: AsyncClient) -> None:
    ready = await client.get("/readyz")
    metrics = await client.get("/metrics")

    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert metrics.status_code == 200
    assert "photos_total 0" in metrics.text
