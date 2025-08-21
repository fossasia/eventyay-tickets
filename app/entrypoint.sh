#!/bin/sh

echo "Waiting for postgres..."

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done

echo "PostgreSQL started"

. .venv/bin/activate

python manage.py flush --no-input
python manage.py migrate

exec "$@"
