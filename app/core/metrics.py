from prometheus_client import Counter, Histogram

# --- API metrics ---

photos_uploaded_total = Counter(
    "photos_uploaded_total",
    "Total number of photos accepted for upload",
)

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)

storage_upload_errors_total = Counter(
    "storage_upload_errors_total",
    "Total number of MinIO upload errors",
)

kafka_publish_errors_total = Counter(
    "kafka_publish_errors_total",
    "Total number of Kafka publish errors",
)

# --- Worker metrics ---

photo_analysis_started_total = Counter(
    "photo_analysis_started_total",
    "Total number of photo analysis attempts started",
)

photo_analysis_completed_total = Counter(
    "photo_analysis_completed_total",
    "Total number of photo analyses completed successfully",
)

photo_analysis_failed_total = Counter(
    "photo_analysis_failed_total",
    "Total number of photo analyses that ended in failed status",
    ["reason"],
)

photo_analysis_duration_seconds = Histogram(
    "photo_analysis_duration_seconds",
    "Duration of a full photo analysis (download + gRPC + persist) in seconds",
)

worker_messages_processed_total = Counter(
    "worker_messages_processed_total",
    "Total number of Kafka messages processed by the worker",
    ["outcome"],
)

analyzer_grpc_errors_total = Counter(
    "analyzer_grpc_errors_total",
    "Total number of gRPC errors returned by the analyzer",
    ["grpc_code"],
)
