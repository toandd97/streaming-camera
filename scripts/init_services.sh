#!/usr/bin/env bash
# Initialize application dependencies and start the backend stack.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

bash scripts/init_env.sh
docker compose up -d --build

echo "[INFO] Waiting for backend readiness"
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/v1/cameras >/dev/null; then
    echo "[OK] Backend is ready at http://localhost:8000"
    exit 0
  fi
  sleep 2
done

echo "[ERROR] Backend did not become ready within 120 seconds" >&2
exit 1
