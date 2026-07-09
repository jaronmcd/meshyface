#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PYTHON}"
elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
else
  PYTHON_BIN="python"
fi

export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-${ROOT_DIR}/.ruff_cache}"

"${PYTHON_BIN}" -m ruff check . --isolated "$@"
