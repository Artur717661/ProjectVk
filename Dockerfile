FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY proto ./proto
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY tests ./tests
COPY tools ./tools

# gRPC stubs are generated from the shared contract BEFORE the project is
# installed, so the installed package already contains them.
RUN uv pip install --system --no-cache grpcio-tools \
    && python -m grpc_tools.protoc \
        -I proto \
        --python_out=app/generated \
        --grpc_python_out=app/generated \
        proto/analyzer.proto \
    && sed -i 's/^import analyzer_pb2 as analyzer__pb2/from . import analyzer_pb2 as analyzer__pb2/' \
        app/generated/analyzer_pb2_grpc.py

RUN uv pip install --system --no-cache ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
