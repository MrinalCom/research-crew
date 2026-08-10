#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"

if [ ! -d .venv ]; then
  echo "Creating virtualenv..."
  if command -v uv >/dev/null 2>&1; then
    uv venv .venv --python 3.12
  else
    python3.13 -m venv .venv || python3 -m venv .venv
  fi
fi

source .venv/bin/activate

if command -v uv >/dev/null 2>&1; then
  uv pip install -e ".[dev]" 2>/dev/null || uv pip install -e . && uv pip install pytest pytest-asyncio httpx
else
  pip install -q -e . -e ".[dev]" 2>/dev/null || pip install -q -e . pytest pytest-asyncio httpx
fi

export $(grep -v '^#' ../.env 2>/dev/null | xargs -0 2>/dev/null) || true
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
