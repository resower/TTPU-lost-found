#!/bin/sh
# One-container start (used on Railway, where services cannot share a SQLite volume).
# Web, bot and worker run together; docker-compose.yml runs them as three containers instead.
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
# Optional first office account: set DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --noinput --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" 2>&1 || true
fi
python manage.py runworker &
if [ -n "$BOT_TOKEN" ]; then
  python manage.py runbot &
fi
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2
