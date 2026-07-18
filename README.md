# Photo Analysis Service

Учебный backend-сервис для загрузки фотографий и подготовки их к
асинхронному анализу. Проект сделан по материалам первых двух воркшопов.

## Что работает сейчас

- FastAPI с REST API;
- PostgreSQL для метаданных и статусов;
- MinIO для байтов фотографий;
- миграция Alembic;
- единый формат ошибок;
- `request_id` в ответах и логах;
- подготовленный gRPC/Protobuf-контракт analyzer-а;
- Docker Compose для локального запуска.

Kafka, worker, Prometheus, Grafana и Kubernetes пока не реализованы: они входят
в следующие воркшопы и описаны в [архитектуре](docs/architecture.md).

## Быстрый запуск

```bash
cp .env.example .env
docker compose up --build
```

После запуска:

- API: <http://localhost:8080>
- Swagger: <http://localhost:8080/docs>
- MinIO Console: <http://localhost:9001>

Локальные данные хранятся в Docker volumes. Чтобы удалить их после эксперимента:

```bash
docker compose down -v
```

## Проверка API

```bash
curl http://localhost:8080/healthz
curl -X POST http://localhost:8080/v1/photos -F "file=@./photo.jpg"
curl http://localhost:8080/v1/photos
```

Полный список ручек и примеры ответов находятся в [docs/api.md](docs/api.md).

## Запуск тестов локально

Нужен Python 3.12 и виртуальное окружение:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Тесты используют SQLite и подменённое файловое хранилище, поэтому для их
запуска не требуется поднимать Docker.

## Структура

```text
app/
  api/             HTTP-ручки, middleware и ошибки
  core/            настройки, зависимости и логи
  db/              модели и подключение к PostgreSQL
  integrations/    MinIO
  repositories/    SQL-запросы
  schemas/         Pydantic-контракты
  services/        бизнес-сценарии
alembic/           миграции
docs/              архитектура и API
proto/             контракт analyzer-а
tests/             тесты API
```

## Как устроен upload

`POST /v1/photos` сначала проверяет файл, затем сохраняет его в MinIO и создаёт
строку в PostgreSQL со статусом `pending`. В ответ клиент сразу получает
`202 Accepted`. Позже между сохранением и обработкой появится Kafka.
