#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
ENV_FILE="$BACKEND_DIR/.env"

if [ "${1:-}" = "" ]; then
  echo "Usage: bash scripts/switch_to_tencent_db.sh 'postgresql://user:password@host:5432/dbname?sslmode=require'"
  exit 1
fi

DB_URL="$1"
if [[ "$DB_URL" != postgresql://* && "$DB_URL" != postgresql+psycopg2://* ]]; then
  echo "Error: DATABASE_URL must start with postgresql:// or postgresql+psycopg2://"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  cp "$BACKEND_DIR/.env.example" "$ENV_FILE"
fi

TMP_FILE="$(mktemp)"
UPDATED=0
while IFS= read -r line || [ -n "$line" ]; do
  if [[ "$line" == DATABASE_URL=* ]]; then
    printf 'DATABASE_URL=%s\n' "$DB_URL" >> "$TMP_FILE"
    UPDATED=1
  else
    printf '%s\n' "$line" >> "$TMP_FILE"
  fi
done < "$ENV_FILE"

if [ "$UPDATED" -eq 0 ]; then
  printf '\nDATABASE_URL=%s\n' "$DB_URL" >> "$TMP_FILE"
fi

mv "$TMP_FILE" "$ENV_FILE"

PID="$(lsof -tiTCP:8000 -sTCP:LISTEN | head -n1 || true)"
if [ -n "$PID" ]; then
  kill "$PID"
  sleep 1
fi

PY_BIN="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PY_BIN" ]; then
  PY_BIN="$BACKEND_DIR/.venv/bin/python"
fi

if [ ! -x "$PY_BIN" ]; then
  echo "Error: Python executable not found in $ROOT_DIR/.venv or $BACKEND_DIR/.venv"
  exit 1
fi

cd "$BACKEND_DIR"
nohup "$PY_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >/tmp/backend_uvicorn.log 2>&1 &
sleep 2

if ! curl -fsS http://127.0.0.1:8000/health >/tmp/backend_health_after_switch.json 2>&1; then
  echo "Backend failed to start. Last logs:"
  tail -n 80 /tmp/backend_uvicorn.log || true
  exit 1
fi

if ! curl -fsS http://127.0.0.1:8000/api/v1/store/health/db >/tmp/backend_db_health_after_switch.json 2>&1; then
  echo "DB health check failed. Last logs:"
  tail -n 80 /tmp/backend_uvicorn.log || true
  exit 1
fi

echo "Switched DATABASE_URL and restarted backend successfully."
echo "- Health: /tmp/backend_health_after_switch.json"
echo "- DB Health: /tmp/backend_db_health_after_switch.json"
