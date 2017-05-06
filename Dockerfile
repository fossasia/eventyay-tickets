FROM python:3.6

RUN apt-get update && apt-get install -y git gettext \
	libmysqlclient-dev libpq-dev locales libmemcached-dev build-essential \
	--no-install-recommends && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/* && \
    dpkg-reconfigure locales && \
	locale-gen C.UTF-8 && \
	/usr/sbin/update-locale LANG=C.UTF-8

ENV LC_ALL C.UTF-8

COPY docker/pretalx.bash /usr/local/bin/pretalx
COPY src /src

RUN mkdir /static && \
    cd /src && \
    pip3 install -U pip setuptools wheel typing && \
    pip3 install -r requirements.txt && \
    pip3 install -r requirements/optional.txt && \
    pip3 install gunicorn && \
    python3 manage.py collectstatic --noinput && \
    python3 manage.py compress && \
    python3 manage.py compilemessages && \
    chmod +x /usr/local/bin/pretalx

RUN mkdir /data
VOLUME /data

EXPOSE 80
ENTRYPOINT ["/usr/local/bin/pretalx"]
