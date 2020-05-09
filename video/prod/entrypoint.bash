#!/bin/bash
cd /venueless/server || exit
export DJANGO_SETTINGS_MODULE=venueless.settings
export VENUELESS_DATA_DIR=/data/
export HOME=/venueless
export NUM_WORKERS=${VENUELESS_WORKERS:-$((2 * $(nproc --all)))}

if [ ! -d /data/logs ]; then
    mkdir /data/logs;
fi
if [ ! -d /data/media ]; then
    mkdir /data/media;
fi

python3 manage.py migrate --noinput

if [ "$1" == "all" ]; then
    exec sudo /usr/bin/supervisord -n -c /etc/supervisord.conf
fi

if [ "$1" == "webworker" ]; then
    exec gunicorn -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000 --bind unix:/run/venueless/websocket.sock --max-requests 1200 --max-requests-jitter 200  -w "$NUM_WORKERS" venueless.asgi:application
fi

if [ "$1" == "shell" ]; then
    exec python3 manage.py shell_plus
fi

exec python3 manage.py "$@"