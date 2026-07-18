FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
       "alembic>=1.13,<2.0" \
       "asyncpg>=0.29,<1.0" \
       "fastapi>=0.115,<1.0" \
       "minio>=7.2,<8.0" \
       "pydantic-settings>=2.6,<3.0" \
       "python-multipart>=0.0.17,<1.0" \
       "sqlalchemy[asyncio]>=2.0,<3.0" \
       "uvicorn[standard]>=0.32,<1.0"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini pyproject.toml ./

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
