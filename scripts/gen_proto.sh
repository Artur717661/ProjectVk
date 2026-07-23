#!/usr/bin/env sh
# Regenerates app/generated/analyzer_pb2*.py from proto/analyzer.proto.
# Run from the photo-service/ directory (this is also done automatically
# during the Docker image build).
set -e

python -m grpc_tools.protoc \
    -I proto \
    --python_out=app/generated \
    --grpc_python_out=app/generated \
    proto/analyzer.proto

# grpc_tools generates a plain `import analyzer_pb2 as analyzer__pb2`, which
# only works if app/generated is on sys.path directly. Rewrite it to a proper
# relative import so `app.generated` behaves like a normal package.
sed -i.bak 's/^import analyzer_pb2 as analyzer__pb2/from . import analyzer_pb2 as analyzer__pb2/' \
    app/generated/analyzer_pb2_grpc.py
rm -f app/generated/analyzer_pb2_grpc.py.bak

echo "Generated app/generated/analyzer_pb2.py and analyzer_pb2_grpc.py"
