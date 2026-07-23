from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://photo:photo@postgres:5432/photo"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "photos"
    minio_secure: bool = False

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic: str = "photo.analysis.requested"
    kafka_consumer_group: str = "photo-analysis-worker"

    analyzer_addr: str = "45.132.19.101:50051"
    analyzer_timeout_seconds: float = 30.0
    analyzer_max_retries: int = 3
    analyzer_max_message_mb: int = 32

    log_level: str = "INFO"
    max_upload_mb: int = 20

    perceptual_hash_hamming_threshold: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
