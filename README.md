# Photo Analysis Service

Учебный кейс «Облако Mail»: backend для загрузки фото, асинхронного анализа
через внешний gRPC-сервис и хранения результатов. Фронтенда нет — только API
+ Swagger.

## Стек

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy (async) + asyncpg, Alembic,
PostgreSQL, MinIO, aiokafka, grpcio, prometheus-client, structlog, uv.

## Архитектура

```
api → services → repositories / integrations
```

- `app/api` — только HTTP-обвязка, SQL здесь запрещён.
- `app/services` — бизнес-логика (валидация, оркестрация storage/kafka/repo).
- `app/repositories` — весь SQL живёт тут.
- `app/integrations` — MinIO, Kafka producer, gRPC-клиент analyzer'а.
- `app/worker` — отдельный процесс: Kafka consumer, вызывает analyzer, пишет
  результат в БД.

Поток: `POST /v1/photos` → валидация → sha256 → MinIO → `INSERT photos(status=pending)`
→ publish в Kafka → `202`. Воркер вычитывает сообщение, атомарно переводит
`pending → processing`, скачивает байты из MinIO, шлёт их в gRPC analyzer,
сохраняет результат (`done`/`failed`), группирует дубликаты по
perceptual-hash (расстояние Хэмминга ≤ 10) в `duplicate_groups`.

## Быстрый старт

```bash
docker compose up -d --build
```

Поднимутся: `api` (51201), `worker`, `postgres`, `minio` (консоль 51203),
`kafka`+`zookeeper`, `prometheus` (51204), `grafana` (51202). Перед стартом
`api`/`worker` отрабатывает одноразовый сервис `migrate` (`alembic upgrade head`).

Проверить:

```bash
curl http://localhost:51201/healthz
curl http://localhost:51201/readyz
curl -F "file=@photo.jpg" http://localhost:51201/v1/photos
```

Swagger: http://localhost:51201/docs
Grafana: http://localhost:51202 (admin/admin)
Prometheus: http://localhost:51204
MinIO Console: http://localhost:51203 (minioadmin/minioadmin)

## Переменные окружения

`.env` уже создан из `.env.example` со значениями по умолчанию для
docker-compose. Таблица:

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `DATABASE_URL` | async DSN для Postgres | `postgresql+asyncpg://photo:photo@postgres:5432/photo` |
| `MINIO_ENDPOINT` | host:port MinIO | `minio:9000` |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | доступ к MinIO | `minioadmin` / `minioadmin` |
| `MINIO_BUCKET` | бакет для оригиналов | `photos` |
| `MINIO_SECURE` | TLS для MinIO | `false` |
| `KAFKA_BOOTSTRAP_SERVERS` | брокеры Kafka | `kafka:9092` |
| `KAFKA_TOPIC` | топик запросов на анализ | `photo.analysis.requested` |
| `KAFKA_CONSUMER_GROUP` | consumer group воркера | `photo-analysis-worker` |
| `ANALYZER_ADDR` | адрес внешнего gRPC-analyzer | `45.132.19.101:50051` |
| `ANALYZER_TIMEOUT_SECONDS` | deadline на вызов | `30` |
| `ANALYZER_MAX_RETRIES` | попыток на transient-ошибки | `3` |
| `ANALYZER_MAX_MESSAGE_MB` | лимит размера сообщения gRPC | `32` |
| `LOG_LEVEL` | уровень логирования | `INFO` |
| `MAX_UPLOAD_MB` | лимит размера загружаемого файла | `20` |
| `PERCEPTUAL_HASH_HAMMING_THRESHOLD` | порог схожести для дублей | `10` |

Секретов в коде нет — всё через `.env`.

## API

| Метод | Путь | Описание |
|---|---|---|
| POST | `/v1/photos` | Загрузка файла (multipart), 202 `{photo_id, status}` |
| GET | `/v1/photos` | Список фото |
| GET | `/v1/photos/{id}` | Статус + результаты анализа |
| GET | `/v1/photos/{id}/content` | Байты оригинала из MinIO |
| GET | `/healthz` | Liveness |
| GET | `/readyz` | Readiness (проверяет БД/MinIO/Kafka) |
| GET | `/metrics` | Prometheus-метрики |

Коды ошибок: `415` не изображение, `413` слишком большой файл, `404` не
найдено, `503` MinIO/Kafka недоступны, `500` прочее. Формат ошибки единый:

```json
{"error": {"code": "photo_not_found", "message": "..."}, "request_id": "..."}
```

## gRPC-контракт analyzer'а

Внешний сервис не меняем, только читаем `proto/analyzer.proto`. Стабы
(`analyzer_pb2.py`, `analyzer_pb2_grpc.py`) генерируются автоматически на
этапе сборки Docker-образов (`RUN python -m grpc_tools.protoc ...` в
`Dockerfile`/`Dockerfile.worker`) и **не коммитятся** в репозиторий — они
всегда актуальны относительно `proto/analyzer.proto`.

Для локальной разработки без Docker (нужен установленный Python + `uv sync`):

```bash
sh scripts/gen_proto.sh
```

Локальный офлайн-заменитель реального analyzer'а — `tools/mock_analyzer.py`
(тот же .proto, используется в тестах и для ручной проверки без доступа к
`45.132.19.101:50051`).

## Метрики

API: `photos_uploaded_total`, `http_requests_total`, `http_request_duration_seconds`,
`storage_upload_errors_total`, `kafka_publish_errors_total`.

Worker: `photo_analysis_started_total`, `photo_analysis_completed_total`,
`photo_analysis_failed_total`, `photo_analysis_duration_seconds`,
`worker_messages_processed_total`, `analyzer_grpc_errors_total`.

## Тесты

Тесты дергают Postgres/сеть контейнеров, поэтому запускаются внутри сети
docker-compose (Postgres/Kafka/MinIO не публикуют порты на хост):

```bash
docker compose run --rm api pytest -v
```

БД для тестов — отдельная `photo_test` (создаётся автоматически при первом
старте `postgres` через `scripts/init-test-db.sql`), поэтому тесты не трогают
данные из `photo`, с которой работают живые `api`/`worker`. Если контейнер
`postgres` уже поднимался раньше без этого скрипта (том с данными создан до
обновления), накатите её вручную одной командой:

```bash
docker compose exec postgres psql -U photo -c "CREATE DATABASE photo_test;"
```

Покрытие: happy path загрузки, 415/413/404, ретраи gRPC-клиента на
transient-кодах и их отсутствие на `INVALID_ARGUMENT`, атомарный переход
`pending → processing`.

## Миграции

Только Alembic, `create_all` не используется в рантайме:

```bash
docker compose run --rm api alembic revision --autogenerate -m "message"
docker compose run --rm api alembic upgrade head
```
