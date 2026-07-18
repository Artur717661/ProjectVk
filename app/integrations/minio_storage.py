import asyncio
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.core.exceptions import DependencyUnavailableError


class MinioStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    async def ensure_bucket(self) -> None:
        try:
            exists = await asyncio.to_thread(self.client.bucket_exists, self.bucket)
            if not exists:
                await asyncio.to_thread(self.client.make_bucket, self.bucket)
        except S3Error as exc:
            raise DependencyUnavailableError("Не удалось подготовить MinIO") from exc

    async def put_bytes(self, object_key: str, content: bytes, content_type: str) -> None:
        try:
            await self.ensure_bucket()
            stream = BytesIO(content)
            await asyncio.to_thread(
                self.client.put_object,
                self.bucket,
                object_key,
                stream,
                len(content),
                content_type=content_type,
            )
        except (S3Error, OSError) as exc:
            raise DependencyUnavailableError("Не удалось сохранить файл в MinIO") from exc

    async def get_bytes(self, object_key: str) -> bytes:
        def read_object() -> bytes:
            response = self.client.get_object(self.bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        try:
            return await asyncio.to_thread(read_object)
        except (S3Error, OSError) as exc:
            raise DependencyUnavailableError("Не удалось прочитать файл из MinIO") from exc

    async def delete(self, object_key: str) -> None:
        try:
            await asyncio.to_thread(self.client.remove_object, self.bucket, object_key)
        except (S3Error, OSError) as exc:
            raise DependencyUnavailableError("Не удалось удалить файл из MinIO") from exc
