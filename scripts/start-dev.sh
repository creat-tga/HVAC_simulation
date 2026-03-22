#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

START_BACKEND=true
START_FRONTEND=true

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --backend) START_FRONTEND=false; shift ;;
    --frontend) START_BACKEND=false; shift ;;
    *) shift ;;
  esac
done

if [ "$START_BACKEND" = true ]; then
  echo "Starting backend in background (cwd: $ROOT_DIR/backend)"
  (cd "$ROOT_DIR/backend" && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000) &
fi

if [ "$START_FRONTEND" = true ]; then
  echo "Starting frontend (cwd: $ROOT_DIR/frontend)"
  (cd "$ROOT_DIR/frontend" && pnpm run dev) &
fi

wait
