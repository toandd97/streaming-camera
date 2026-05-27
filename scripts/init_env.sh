#!/usr/bin/env bash
# Prepare local configuration required by Docker Compose.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[OK] Created .env from .env.example"
else
  echo "[OK] Using existing .env"
fi

mkdir -p video
echo "[OK] Environment initialization complete"
