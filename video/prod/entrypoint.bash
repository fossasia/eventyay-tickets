#!/bin/bash
cd /venueless/server
export DJANGO_SETTINGS_MODULE=venueless.settings
export VENUELESS_DATA_DIR=/data/
export HOME=/venueless

if [ ! -d /data/logs ]; then
    mkdir /data/logs;
fi
if [ ! -d /data/media ]; then
    mkdir /data/media;
fi

python3 manage.py venueless --noinput

if [ "$1" == "all" ]; then
    exec sudo /usr/bin/supervisord -n -c /etc/supervisord.conf
fi

if [ "$1" == "webworker" ]; then
    exec daphne venueless.routing:application \
        -u /tmp/daphne.sock
fi

if [ "$1" == "shell" ]; then
    exec python3 mange.py shell
fi

echo "Specify argument: all|webworker|shell"
exit 1
