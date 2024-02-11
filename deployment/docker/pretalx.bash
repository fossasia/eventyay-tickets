#!/bin/bash
cd /pretalx/src || exit 1
export PRETALX_DATA_DIR="${PRETALX_DATA_DIR:-/data}"
export HOME=/pretalx

PRETALX_FILESYSTEM_LOGS="${PRETALX_FILESYSTEM_LOGS:-/data/logs}"
PRETALX_FILESYSTEM_MEDIA="${PRETALX_FILESYSTEM_MEDIA:-/data/media}"
PRETALX_FILESYSTEM_STATIC="${PRETALX_FILESYSTEM_STATIC:-/pretalx/src/static.dist}"

GUNICORN_WORKERS="${GUNICORN_WORKERS:-${WEB_CONCURRENCY:-$((2 * $(nproc)))}}"
GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-1200}"
GUNICORN_MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-50}"
GUNICORN_FORWARDED_ALLOW_IPS="${GUNICORN_FORWARDED_ALLOW_IPS:-127.0.0.1}"

AUTOMIGRATE="${AUTOMIGRATE:-yes}"
AUTOREBUILD="${AUTOREBUILD:-yes}"

if [ "$PRETALX_FILESYSTEM_LOGS" != "/data/logs" ]; then
    export PRETALX_FILESYSTEM_LOGS
fi
if [ "$PRETALX_FILESYSTEM_MEDIA" != "/data/media" ]; then
    export PRETALX_FILESYSTEM_MEDIA
fi
if [ "$PRETALX_FILESYSTEM_STATIC" != "/pretalx/src/static.dist" ]; then
    export PRETALX_FILESYSTEM_STATIC
fi

if [ ! -d "$PRETALX_FILESYSTEM_LOGS" ]; then
    mkdir "$PRETALX_FILESYSTEM_LOGS";
fi
if [ ! -d "$PRETALX_FILESYSTEM_MEDIA" ]; then
    mkdir "$PRETALX_FILESYSTEM_MEDIA";
fi
if [ "$PRETALX_FILESYSTEM_STATIC" != "/pretalx/src/static.dist" ] &&
   [ ! -d "$PRETALX_FILESYSTEM_STATIC" ] &&
   [ "$AUTOREBUILD" = "yes" ]; then
    mkdir -p "$PRETALX_FILESYSTEM_STATIC"
    flock --nonblock /pretalx/.lockfile python3 -m pretalx rebuild
fi

if [ "$1" == "cron" ]; then
    exec python3 -m pretalx runperiodic
fi

if [ "$AUTOMIGRATE" = "yes" ]; then
    python3 -m pretalx migrate --noinput
fi

if [ "$1" == "all" ]; then
    exec sudo /usr/bin/supervisord -n -c /etc/supervisord.conf
fi

if [ "$1" == "webworker" ]; then
    exec gunicorn pretalx.wsgi \
        --name pretalx \
        --workers "${GUNICORN_WORKERS}" \
        --max-requests "${GUNICORN_MAX_REQUESTS}" \
        --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER}" \
        --forwarded-allow-ips "${GUNICORN_FORWARDED_ALLOW_IPS}" \
        --log-level=info \
        --bind=0.0.0.0:80
fi

if [ "$1" == "taskworker" ]; then
    exec celery -A pretalx.celery_app worker -l info
fi

if [ "$1" == "shell" ]; then
    exec python3 -m pretalx shell
fi

if [ "$1" == "upgrade" ]; then
    python3 -m pretalx rebuild
    exec python3 -m pretalx regenerate_css
fi

exec python3 -m pretalx "$@"
