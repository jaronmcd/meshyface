#!/usr/bin/env bash
# Render the working-tree dashboard on phone/tablet profiles and audit each view.
#
# Starts a radio-less local server (dead TCP radio, scratch history DB), runs
# scripts/mobile_preview.py against it, then stops the server. Extra arguments are
# passed through to mobile_preview.py (for example --device "iPhone SE" --views chat).
#
# Environment:
#   MESH_MOBILE_PREVIEW_PORT       local server port (default 8898)
#   MESH_MOBILE_PREVIEW_API_FROM   origin to proxy /api/* from, e.g. http://192.0.2.10:8877/
#                                  so the local code renders a running dashboard's data
#   MESH_MOBILE_PREVIEW_OUT        output directory (default benchmarks/mobile_preview/out)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MESH_MOBILE_PREVIEW_PORT:-8898}"
URL="http://127.0.0.1:${PORT}/"
OUT="${MESH_MOBILE_PREVIEW_OUT:-${ROOT_DIR}/benchmarks/mobile_preview/out}"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/mesh_mobile_preview.XXXXXX")"
if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PYTHON}"
elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
else
  PYTHON_BIN="python"
fi
SERVER_PID=""

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

probe() {
  "${PYTHON_BIN}" - "$1" <<'EOF'
import sys, urllib.request
try:
    urllib.request.urlopen(sys.argv[1] + "api/version", timeout=2).read()
except Exception:
    raise SystemExit(1)
EOF
}

if probe "${URL}"; then
  echo "A server already answers at ${URL}; set MESH_MOBILE_PREVIEW_PORT to a free port." >&2
  exit 2
fi

mkdir -p "${SCRATCH}"
"${PYTHON_BIN}" "${ROOT_DIR}/mesh_dashboard.py" \
  --mesh-host 127.0.0.1 \
  --mesh-tcp-port 1 \
  --http-host 127.0.0.1 \
  --http-port "${PORT}" \
  --history-db "${SCRATCH}/history-${PORT}.sqlite3" \
  --file-transfer-enable \
  --accept-file-transfer-traffic-disclaimer \
  --games-enable \
  --plugins-enable \
  >"${SCRATCH}/server-${PORT}.log" 2>&1 &
SERVER_PID="$!"

for _ in $(seq 1 60); do
  if probe "${URL}"; then
    break
  fi
  if ! kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    tail -n 60 "${SCRATCH}/server-${PORT}.log" >&2 || true
    echo "local server failed to start" >&2
    exit 1
  fi
  sleep 1
done
probe "${URL}" || { echo "local server did not answer within 60 s" >&2; exit 1; }

ARGS=(--url "${URL}" --out "${OUT}")
if [[ -n "${MESH_MOBILE_PREVIEW_API_FROM:-}" ]]; then
  ARGS+=(--api-from "${MESH_MOBILE_PREVIEW_API_FROM}")
fi
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/mobile_preview.py" "${ARGS[@]}" "$@"
