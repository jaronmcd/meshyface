#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COVERAGE_MIN="${MESH_LOCAL_COVERAGE_MIN:-85}"

python -m pytest \
  --cov=meshdash \
  --cov=mesh_dashboard \
  --cov=mesh_connection \
  --cov-report=term \
  --cov-fail-under="${COVERAGE_MIN}" \
  "$@"
