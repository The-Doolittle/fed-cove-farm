#!/bin/sh
set -e
python manage.py migrate --noinput
exec gunicorn fedcove.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -
