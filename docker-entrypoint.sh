#!/bin/sh
set -e

# Migrations and superuser bootstrap. Idempotent by design.
# Celery workers bypass this by setting `entrypoint: []` in compose,
# so they never race the backend on migrations.
echo "Running database migrations..."
python manage.py migrate --noinput

echo "Ensuring superuser exists..."
python manage.py create_superuser_env

# Hand off to whatever CMD (or `command:` in compose) asked for
exec "$@"