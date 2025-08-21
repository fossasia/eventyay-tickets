#!/bin/sh

echo "Waiting for postgres..."

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done

echo "PostgreSQL started"

. .env/bin/activate

python manage.py collectstatic --noinput
python manage.py compress
python manage.py migrate

# copy all files from eventyay/static to static
rm -rf static/*
cp -a eventyay/static .

exec "$@"
