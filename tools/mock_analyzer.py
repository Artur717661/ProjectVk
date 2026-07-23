"""Local mock of analyzer.v1.PhotoAnalyzer for offline tests and dev. Run: python -m tools.mock_analyzer"""

import asyncio
import hashlib
import logging

import grpc

from app.generated import analyzer_pb2, analyzer_pb2_grpc

logger = logging.getLogger("mock_analyzer")

MAX_MESSAGE_BYTES = 32 * 1024 * 1024


class MockPhotoAnalyzerServicer(analyzer_pb2_grpc.PhotoAnalyzerServicer):
    """Deterministic fake analysis; object_key __invalid__/__unavailable__ force gRPC errors."""

    async def AnalyzePhoto(self, request: "analyzer_pb2.AnalyzePhotoRequest", context):
        if request.object_key == "__invalid__":
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "malformed request")

        if request.object_key == "__unavailable__":
            await context.abort(grpc.StatusCode.UNAVAILABLE, "analyzer overloaded")

        digest = hashlib.sha1(request.image_bytes[:4096]).hexdigest()
        perceptual_hash = digest[:16]

        return analyzer_pb2.AnalyzePhotoResponse(
            faces_count=1,
            is_blurred=False,
            blur_score=12.5,
            perceptual_hash=perceptual_hash,
            eyes_closed_count=0,
            dominant_color="#336699",
            tags=["mock", "test"],
            model_version="mock-v1",
        )


async def serve(address: str = "0.0.0.0:50051") -> None:
    server = grpc.aio.server(
        options=[
            ("grpc.max_send_message_length", MAX_MESSAGE_BYTES),
            ("grpc.max_receive_message_length", MAX_MESSAGE_BYTES),
        ]
    )
    analyzer_pb2_grpc.add_PhotoAnalyzerServicer_to_server(
        MockPhotoAnalyzerServicer(), server
    )
    server.add_insecure_port(address)
    await server.start()
    logger.info("mock_analyzer_listening address=%s", address)
    await server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
