import uuid
from dataclasses import dataclass

import grpc
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import get_settings
from app.core.errors import (
    AnalyzerInvalidArgumentError,
    AnalyzerTransientError,
    AnalyzerUnknownError,
)
from app.core.metrics import analyzer_grpc_errors_total
from app.generated import analyzer_pb2, analyzer_pb2_grpc

logger = structlog.get_logger(__name__)

_RETRYABLE_CODES = {
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
    grpc.StatusCode.RESOURCE_EXHAUSTED,
    grpc.StatusCode.INTERNAL,
}


@dataclass
class AnalysisResult:
    faces_count: int
    is_blurred: bool
    blur_score: float
    perceptual_hash: str
    eyes_closed_count: int
    dominant_color: str
    tags: list[str]
    model_version: str


class AnalyzerClient:
    """gRPC client for the shared PhotoAnalyzer service; channel is reused across calls."""

    def __init__(self) -> None:
        settings = get_settings()
        self._timeout = settings.analyzer_timeout_seconds
        self._max_attempts = settings.analyzer_max_retries
        max_bytes = settings.analyzer_max_message_mb * 1024 * 1024

        self._channel = grpc.aio.insecure_channel(
            settings.analyzer_addr,
            options=[
                ("grpc.max_send_message_length", max_bytes),
                ("grpc.max_receive_message_length", max_bytes),
            ],
        )
        self._stub = analyzer_pb2_grpc.PhotoAnalyzerStub(self._channel)

    async def close(self) -> None:
        await self._channel.close()

    async def analyze(
        self, *, photo_id: uuid.UUID, object_key: str, image_bytes: bytes
    ) -> AnalysisResult:
        request = analyzer_pb2.AnalyzePhotoRequest(
            photo_id=str(photo_id),
            object_key=object_key,
            image_bytes=image_bytes,
        )

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(AnalyzerTransientError),
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential_jitter(initial=0.5, max=8, jitter=1),
            reraise=True,
        ):
            with attempt:
                return await self._call_once(request)

        # Unreachable: AsyncRetrying either returns or reraises above.
        raise AnalyzerUnknownError("Retry loop exited without a result")

    async def _call_once(
        self, request: "analyzer_pb2.AnalyzePhotoRequest"
    ) -> AnalysisResult:
        try:
            response = await self._stub.AnalyzePhoto(request, timeout=self._timeout)
        except grpc.aio.AioRpcError as exc:
            code = exc.code()
            analyzer_grpc_errors_total.labels(grpc_code=code.name).inc()
            logger.warning(
                "analyzer_grpc_error",
                grpc_code=code.name,
                details=exc.details(),
            )
            if code in _RETRYABLE_CODES:
                raise AnalyzerTransientError(
                    f"Analyzer transient error: {code.name} - {exc.details()}"
                ) from exc
            if code == grpc.StatusCode.INVALID_ARGUMENT:
                raise AnalyzerInvalidArgumentError(
                    f"Analyzer rejected request: {exc.details()}"
                ) from exc
            raise AnalyzerUnknownError(
                f"Analyzer error {code.name}: {exc.details()}"
            ) from exc

        return AnalysisResult(
            faces_count=response.faces_count,
            is_blurred=response.is_blurred,
            blur_score=response.blur_score,
            perceptual_hash=response.perceptual_hash,
            eyes_closed_count=response.eyes_closed_count,
            dominant_color=response.dominant_color,
            tags=list(response.tags),
            model_version=response.model_version,
        )


_analyzer_client: AnalyzerClient | None = None


def get_analyzer_client() -> AnalyzerClient:
    global _analyzer_client
    if _analyzer_client is None:
        _analyzer_client = AnalyzerClient()
    return _analyzer_client
