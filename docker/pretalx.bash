#!/bin/bash
# For use with Docker
set -e

cd /src
export PRETALX_DATA_DIR=/data
python3 -m pretalx migrate

if [ "$1" == "web" ]; then
    exec gunicorn \
        -b '0.0.0.0:80' \
        -w 3 --max-requests 1000 --max-requests-jitter 50 \
        pretalx.wsgi
fi
exec python3 -m pretalx $*
