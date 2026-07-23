import uuid

import grpc
import pytest

from app.core.config import get_settings
from app.core.errors import AnalyzerInvalidArgumentError, AnalyzerTransientError
from app.generated import analyzer_pb2, analyzer_pb2_grpc
from app.integrations.analyzer_client import AnalyzerClient


class _CountingServicer(analyzer_pb2_grpc.PhotoAnalyzerServicer):
    """Fails with a fixed gRPC status for the first N calls, then succeeds."""

    def __init__(self, fail_times: int, fail_code: grpc.StatusCode) -> None:
        self.calls = 0
        self.fail_times = fail_times
        self.fail_code = fail_code

    async def AnalyzePhoto(self, request, context):
        self.calls += 1
        if self.calls <= self.fail_times:
            await context.abort(self.fail_code, "injected failure")
        return analyzer_pb2.AnalyzePhotoResponse(
            faces_count=1, perceptual_hash="abc123", model_version="test"
        )


async def _start_server(servicer):
    server = grpc.aio.server()
    analyzer_pb2_grpc.add_PhotoAnalyzerServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    return server, port


@pytest.mark.asyncio
async def test_retries_exhausted_on_transient_error(monkeypatch):
    servicer = _CountingServicer(fail_times=99, fail_code=grpc.StatusCode.UNAVAILABLE)
    server, port = await _start_server(servicer)

    try:
        monkeypatch.setenv("ANALYZER_ADDR", f"127.0.0.1:{port}")
        monkeypatch.setenv("ANALYZER_MAX_RETRIES", "3")
        get_settings.cache_clear()

        analyzer_client = AnalyzerClient()
        try:
            with pytest.raises(AnalyzerTransientError):
                await analyzer_client.analyze(
                    photo_id=uuid.uuid4(), object_key="k", image_bytes=b"x"
                )
        finally:
            await analyzer_client.close()

        assert servicer.calls == 3
    finally:
        await server.stop(None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_no_retry_on_invalid_argument(monkeypatch):
    servicer = _CountingServicer(
        fail_times=99, fail_code=grpc.StatusCode.INVALID_ARGUMENT
    )
    server, port = await _start_server(servicer)

    try:
        monkeypatch.setenv("ANALYZER_ADDR", f"127.0.0.1:{port}")
        monkeypatch.setenv("ANALYZER_MAX_RETRIES", "3")
        get_settings.cache_clear()

        analyzer_client = AnalyzerClient()
        try:
            with pytest.raises(AnalyzerInvalidArgumentError):
                await analyzer_client.analyze(
                    photo_id=uuid.uuid4(), object_key="k", image_bytes=b"x"
                )
        finally:
            await analyzer_client.close()

        assert servicer.calls == 1
    finally:
        await server.stop(None)
        get_settings.cache_clear()
