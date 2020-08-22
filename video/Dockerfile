FROM python:3.8

RUN curl -sL https://deb.nodesource.com/setup_14.x | bash && \
    apt-get install -y --no-install-recommends \
            build-essential \
            git \
            locales \
            libpq-dev \
            libssl-dev \
            libxml2-dev \
            libxslt1-dev \
            nginx \
            python3-dev \
            sudo \
            supervisor \
            nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    dpkg-reconfigure locales && \
	locale-gen C.UTF-8 && \
	/usr/sbin/update-locale LANG=C.UTF-8 && \
    mkdir /etc/venueless && \
    mkdir -p /venueless/webapp && \
    mkdir /data && \
    useradd -ms /bin/bash -d /venueless -u 15371 venueless && \
    echo 'venueless ALL=(ALL) NOPASSWD:SETENV: /usr/bin/supervisord' >> /etc/sudoers && \
    mkdir /static

ENV LC_ALL=C.UTF-8 \
    DJANGO_SETTINGS_MODULE=venueless.settings \
	IPYTHONDIR=/data/.ipython

# To copy only the requirements files needed to install from PIP
COPY server/requirements.txt /requirements.txt
RUN pip3 install -U pip wheel setuptools && \
    pip3 install -Ur /requirements.txt ipython && \
    rm -rf ~/.cache/pip

COPY prod/entrypoint.bash /usr/local/bin/venueless
COPY prod/supervisord.conf /etc/supervisord.conf
COPY prod/nginx.conf /etc/nginx/nginx.conf

RUN chmod +x /usr/local/bin/venueless

COPY webapp/.* /venueless/webapp/
COPY webapp/*.js /venueless/webapp/
COPY webapp/*.json /venueless/webapp/
COPY webapp/src/ /venueless/webapp/src/
COPY webapp/public/ /venueless/webapp/public/

RUN cd /venueless/webapp && \
    npm ci && \
    npm run build && \
	mkdir -p data && \
	cd .. && \
    chown -R venueless:venueless /venueless /data

COPY server /venueless/server

ARG COMMIT=""
LABEL commit=${COMMIT}
ENV VENUELESS_COMMIT_SHA=${COMMIT}

USER venueless
VOLUME ["/etc/venueless", "/data"]
EXPOSE 80
ENTRYPOINT ["venueless"]
CMD ["all"]

