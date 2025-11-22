#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="generated"
mkdir -p "$OUT_DIR"

python3 -m grpc_tools.protoc \
  -Iproto \
  --python_out="$OUT_DIR" \
  --grpc_python_out="$OUT_DIR" \
  proto/common.proto \
  proto/match.proto \
  proto/team.proto \
  proto/user.proto \
  proto/feature.proto \
  proto/model.proto \
  proto/prediction.proto
