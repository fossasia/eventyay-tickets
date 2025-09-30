#!/bin/sh

echo "Waiting for postgres..."

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done

echo "PostgreSQL started"

echo "============== running collectstatic ================"
python manage.py collectstatic --noinput
echo "============== running compress ====================="
# collectstatic drops exe bit, but compress needs it
chmod ugo+x /home/app/web/eventyay/static.dist/node_prefix/node_modules/rollup/dist/bin/rollup
python manage.py compress
#echo "============== running collectstatic a SECOND TIME ================"
#echo "THIS SHOULD NOT BE NECESSARY, but compress creates files in static instead of static.dist"
#python manage.py collectstatic --noinput
echo "============== running migrate ======================"
python manage.py migrate

exec "$@"
