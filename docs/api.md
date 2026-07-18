# API первого MVP

Все публичные ручки находятся под `/v1`.

## Загрузка фотографии

```bash
curl -X POST http://localhost:8080/v1/photos \
  -F "file=@./photo.jpg"
```

Ответ: `202 Accepted`

```json
{
  "photo_id": "9c6c8f2d-5a0c-4c2f-baa3-4881c3a6c1e4",
  "status": "pending"
}
```

## Список фотографий

```bash
curl http://localhost:8080/v1/photos
```

## Одна фотография

```bash
curl http://localhost:8080/v1/photos/{photo_id}
```

## Содержимое фотографии

```bash
curl http://localhost:8080/v1/photos/{photo_id}/content --output photo.jpg
```

## Состояние сервиса

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz
curl http://localhost:8080/metrics
```

`/healthz` проверяет, что API отвечает. `/readyz` дополнительно проверяет
подключение к PostgreSQL. `/metrics` отдаёт небольшой Prometheus-совместимый
счётчик фотографий без отдельного сервиса мониторинга.

## Ошибка

```json
{
  "code": "photo_not_found",
  "message": "Фотография не найдена",
  "request_id": "r_456"
}
```
