FROM python:3.11-bookworm
ARG UID=999
ARG GID=999

RUN apt-get update && \
    apt-get install -y git gettext libpq-dev locales libmemcached-dev build-essential \
            supervisor \
            sudo \
            locales \
            less \
            --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    dpkg-reconfigure locales && \
    locale-gen C.UTF-8 && \
    /usr/sbin/update-locale LANG=C.UTF-8 && \
    mkdir /etc/pretalx && \
    mkdir /data && \
    mkdir /public && \
    groupadd -g $GID pretalxuser && \
    useradd -r -u $UID -g pretalxuser -d /pretalx -ms /bin/bash pretalxuser && \
    echo 'pretalxuser ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

ENV LC_ALL=C.UTF-8
# Tell uv to install packages to system, not virtual environment.
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV BASE_PATH=/talk

COPY pyproject.toml /pretalx
COPY uv.lock /pretalx
COPY src /pretalx/src
COPY deployment/docker/pretalx.bash /usr/local/bin/pretalx
COPY deployment/docker/supervisord.conf /etc/supervisord.conf

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# RUN pip3 install -U pip setuptools wheel typing && \
#     pip3 install -e /pretalx/[postgres,redis] && \
#     pip3 install pylibmc && \
#     pip3 install gunicorn

WORKDIR /pretalx
RUN uv sync --frozen --all-extras --no-install-project

RUN uv run -m pretalx makemigrations
RUN uv run -m pretalx migrate

RUN apt-get update && \
    apt-get install -y nodejs npm && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    uv run -m pretalx rebuild

RUN chmod +x /usr/local/bin/pretalx && \
    cd /pretalx/src && \
    rm -f pretalx.cfg && \
    chown -R pretalxuser:pretalxuser /pretalx /data /public && \
    rm -f /pretalx/src/data/.secret

USER pretalxuser
VOLUME ["/etc/pretalx", "/data", "/public"]
EXPOSE 80
ENTRYPOINT ["pretalx"]
CMD ["all"]
