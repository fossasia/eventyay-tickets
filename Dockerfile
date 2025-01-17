FROM python:3.11-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# The project will stay in this directory
WORKDIR /pretix

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
            curl \
            build-essential \
            gettext \
            git \
            libffi-dev \
            libjpeg-dev \
            libmemcached-dev \
            libpq-dev \
            libssl-dev \
            libxml2-dev \
            libxslt1-dev \
            locales \
            nginx \
            python3-virtualenv \
            python3-dev \
            sudo \
            supervisor \
            zlib1g-dev \
            npm && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    dpkg-reconfigure locales && \
	locale-gen C.UTF-8 && \
	/usr/sbin/update-locale LANG=C.UTF-8 && \
    mkdir /etc/pretix && \
    mkdir /data && \
    useradd -ms /bin/bash -d /pretix -u 15371 pretixuser && \
    echo 'pretixuser ALL=(ALL) NOPASSWD:SETENV: /usr/bin/supervisord' >> /etc/sudoers && \
    mkdir /static && \
    mkdir /etc/supervisord

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8
ARG GITHUB_TOKEN
ENV GITHUB_TOKEN=$GITHUB_TOKEN
# Settings for uv: enable bytecode compilation;
# copy from the cache instead of linking since it's a mounted volume.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/usr/local

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --all-extras --no-dev

COPY deployment/docker/pretix.bash /usr/local/bin/pretix
COPY deployment/docker/supervisord /etc/supervisord
COPY deployment/docker/supervisord.all.conf /etc/supervisord.all.conf
COPY deployment/docker/supervisord.web.conf /etc/supervisord.web.conf
COPY deployment/docker/nginx.conf /etc/nginx/nginx.conf
COPY deployment/docker/production_settings.py /pretix/src/production_settings.py
COPY pyproject.toml /pretix/pyproject.toml
COPY uv.lock /pretix/uv.lock
COPY src /pretix/src

# RUN pip3 install -U \
#         pip \
#         setuptools \
#         toml \
#         wheel && \
#     cd /pretix && \
#     PRETIX_DOCKER_BUILD=TRUE pip3 install \
#         -e ".[memcached]" \
#         gunicorn django-extensions ipython && \
#     rm -rf ~/.cache/pip

ENV DJANGO_SETTINGS_MODULE=production_settings

RUN chmod +x /usr/local/bin/pretix && \
    rm /etc/nginx/sites-enabled/default && \
    cd /pretix/src && \
    rm -f pretix.cfg && \
    mkdir -p data && \
    chown -R pretixuser:pretixuser /pretix /data data && \
    sudo -u pretixuser make production

USER pretixuser
VOLUME ["/etc/pretix", "/data"]
EXPOSE 80
ENTRYPOINT ["pretix"]
CMD ["all"]
