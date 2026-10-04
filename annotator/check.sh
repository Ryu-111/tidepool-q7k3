#!/usr/bin/env bash
# Every static check and test of the annotator; exits non-zero on the first failure.
set -euo pipefail
cd "$(dirname "$0")"

uv run ruff format --check
uv run ruff check
uv run mypy
uv run pytest -q

cd web
npm ci --silent
npm run -s typecheck
npm run -s lint
npm run -s build
