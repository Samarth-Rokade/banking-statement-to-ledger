#!/bin/sh
set -e

# Off by default: running migrations from every container start risks multiple
# instances racing `alembic upgrade head` concurrently on a cold deploy. The
# recommended path (see DEPLOY.md) is a one-off migration step run once before
# rolling out a new revision; RUN_MIGRATIONS_ON_START exists for simple
# single-instance setups that would rather not manage that extra step.
if [ "${RUN_MIGRATIONS_ON_START:-false}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi

# Cloud Run injects PORT; default to 8080 (Cloud Run's convention) for parity
# when running the image locally.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
