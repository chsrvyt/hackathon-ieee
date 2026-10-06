#!/bin/sh
# Container entrypoint: migrate, optionally seed demo data, then serve.
set -e
echo "Running database migrations..."
alembic upgrade head
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  echo "Seeding demo data (idempotent)..."
  python -m app.seed
fi
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
  --no-server-header
