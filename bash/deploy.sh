#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV="${VENV:-.venv}"
PY="$VENV/bin/python"

echo "==> Установка зависимостей"
"$VENV/bin/pip" install -r requirements.txt

echo "==> Линт и типы"
"$VENV/bin/ruff" check .
"$VENV/bin/mypy" || true

echo "==> Миграции БД"
"$VENV/bin/alembic" upgrade head

echo "==> Тесты"
"$PY" -m pytest -q

echo "==> Готово"
