#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8001}"
VLLM_BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}"

BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python executable at $PYTHON_BIN"
  echo "Set PYTHON_BIN or create the virtualenv first."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not installed or not on PATH."
  exit 1
fi

cleanup() {
  local code=$?
  trap - EXIT INT TERM

  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  wait 2>/dev/null || true
  exit "$code"
}

trap cleanup EXIT INT TERM

echo "Starting FastAPI backend on ${BACKEND_HOST}:${BACKEND_PORT} (proxy -> ${VLLM_BASE_URL})"
(
  cd "$BACKEND_DIR"
  BACKEND_MODE=proxy VLLM_BASE_URL="$VLLM_BASE_URL" BACKEND_PORT="$BACKEND_PORT" \
    "$PYTHON_BIN" -m uvicorn main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --reload
) &
BACKEND_PID=$!

echo "Starting Vite frontend on default dev port (usually 5173)"
(
  cd "$FRONTEND_DIR"
  VITE_BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}" npm run dev
) &
FRONTEND_PID=$!

wait -n "$BACKEND_PID" "$FRONTEND_PID"
