#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT/backend"
python -m compileall -q app
python -m pytest -q
cd "$ROOT/frontend"
npm run build
cd "$ROOT"
python scripts/evaluate.py

