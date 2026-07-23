import asyncio
import json
import signal
import time
import uuid

import structlog
from aiokafka import AIOKafkaConsumer
from prometheus_client import start_http_server

from app.core.config import get_settings
from app.core.errors import (
    AnalyzerError,
    AnalyzerInvalidArgumentError,
    StorageUnavailableError,
)
from app.core.logging import configure_logging
from app.core.metrics import (
    photo_analysis_completed_total,
    photo_analysis_duration_seconds,
    photo_analysis_failed_total,
    photo_analysis_started_total,
    worker_messages_processed_total,
)
from app.db.models import PhotoStatus
from app.db.session import AsyncSessionLocal
from app.integrations.analyzer_client import AnalyzerClient
from app.integrations.storage import StorageClient
from app.repositories.photo_repository import PhotoRepository

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)

WORKER_METRICS_PORT = 8000


def hamming_distance(hash_a: str, hash_b: str) -> int:
    try:
        int_a = int(hash_a, 16)
        int_b = int(hash_b, 16)
    except (ValueError, TypeError):
        return max(len(hash_a or ""), len(hash_b or "")) * 4
    return bin(int_a ^ int_b).count("1")


async def _handle_duplicates(
    repo: PhotoRepository, photo_id: uuid.UUID, perceptual_hash: str | None
) -> None:
    if not perceptual_hash:
        return

    candidates = await repo.get_hash_candidates(exclude_photo_id=photo_id)
    matches = [
        (candidate_id, group_id)
        for candidate_id, candidate_hash, group_id in candidates
        if hamming_distance(candidate_hash, perceptual_hash)
        <= settings.perceptual_hash_hamming_threshold
    ]
    if not matches:
        return

    existing_group_id = next((g for _, g in matches if g is not None), None)
    if existing_group_id is None:
        group = await repo.create_duplicate_group()
        existing_group_id = group.id

    photo_ids = [photo_id] + [candidate_id for candidate_id, _ in matches]
    await repo.assign_duplicate_group(photo_ids, existing_group_id)
    logger.info(
        "duplicate_group_assigned",
        photo_id=str(photo_id),
        duplicate_group_id=str(existing_group_id),
        matched_count=len(matches),
    )


async def process_message(
    repo: PhotoRepository,
    storage: StorageClient,
    analyzer_client: AnalyzerClient,
    payload: dict,
) -> None:
    photo_id = uuid.UUID(payload["photo_id"])
    object_key = payload["object_key"]
    trace_id = payload.get("trace_id", "unknown")

    structlog.contextvars.bind_contextvars(photo_id=str(photo_id), trace_id=trace_id)

    claimed = await repo.try_mark_processing(photo_id)
    if not claimed:
        logger.info("worker_skip_already_claimed")
        worker_messages_processed_total.labels(outcome="skipped").inc()
        return

    photo_analysis_started_total.inc()
    start = time.perf_counter()

    try:
        image_bytes = await storage.download(object_key)
    except StorageUnavailableError as exc:
        await repo.mark_failed(
            photo_id, error_code="storage_unavailable", error_message=str(exc)
        )
        photo_analysis_failed_total.labels(reason="storage_unavailable").inc()
        worker_messages_processed_total.labels(outcome="failed").inc()
        logger.warning("worker_storage_download_failed", error=str(exc))
        return

    try:
        result = await analyzer_client.analyze(
            photo_id=photo_id, object_key=object_key, image_bytes=image_bytes
        )
    except AnalyzerInvalidArgumentError as exc:
        await repo.mark_failed(
            photo_id, error_code=exc.code, error_message=exc.message
        )
        photo_analysis_failed_total.labels(reason=exc.code).inc()
        worker_messages_processed_total.labels(outcome="failed").inc()
        logger.warning("worker_analyzer_invalid_argument", error=exc.message)
        return
    except AnalyzerError as exc:
        await repo.mark_failed(
            photo_id, error_code=exc.code, error_message=exc.message
        )
        photo_analysis_failed_total.labels(reason=exc.code).inc()
        worker_messages_processed_total.labels(outcome="failed").inc()
        logger.warning("worker_analyzer_error", error=exc.message)
        return

    await repo.mark_done(
        photo_id,
        faces_count=result.faces_count,
        eyes_closed_count=result.eyes_closed_count,
        is_blurred=result.is_blurred,
        blur_score=result.blur_score,
        perceptual_hash=result.perceptual_hash,
        dominant_color=result.dominant_color,
        tags=result.tags,
        model_version=result.model_version,
    )

    await _handle_duplicates(repo, photo_id, result.perceptual_hash)

    photo_analysis_duration_seconds.observe(time.perf_counter() - start)
    photo_analysis_completed_total.inc()
    worker_messages_processed_total.labels(outcome="done").inc()
    logger.info("worker_photo_analysis_done", status=PhotoStatus.done.value)


async def run() -> None:
    start_http_server(WORKER_METRICS_PORT, addr="0.0.0.0")
    logger.info("worker_metrics_server_started", port=WORKER_METRICS_PORT)

    consumer = AIOKafkaConsumer(
        settings.kafka_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    analyzer_client = AnalyzerClient()
    storage = StorageClient()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass  # signal handlers are not available on some platforms

    await consumer.start()
    logger.info("worker_started", topic=settings.kafka_topic)

    try:
        while not stop_event.is_set():
            try:
                record = await asyncio.wait_for(consumer.getone(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except Exception:  # noqa: BLE001
                logger.exception("worker_consumer_poll_failed")
                await asyncio.sleep(1)
                continue

            # Commit only after a terminal outcome, so a crash mid-flight redelivers the message.
            async with AsyncSessionLocal() as session:
                repo = PhotoRepository(session)
                try:
                    await process_message(repo, storage, analyzer_client, record.value)
                except Exception:  # noqa: BLE001
                    structlog.contextvars.clear_contextvars()
                    logger.exception("worker_unhandled_error")
                    worker_messages_processed_total.labels(outcome="error").inc()
                    continue
            structlog.contextvars.clear_contextvars()

            await consumer.commit()
    finally:
        await consumer.stop()
        await analyzer_client.close()
        logger.info("worker_stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
