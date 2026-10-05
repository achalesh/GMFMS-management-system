#!/bin/sh
set -eu
python manage.py check --deploy --fail-level WARNING
python manage.py migrate --check
python manage.py collectstatic --noinput
exec gunicorn --config deploy/gunicorn.conf.py config.wsgi:application
