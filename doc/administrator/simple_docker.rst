Simple installation using Docker
================================

This guide helps you to install pretalx using a single docker container. The exact details of this
might change once we approach the first stable release, so be sure to check back here for major
changes from time to time.

We tested this guide on the Linux distribution **Debian 8.0** but it should work similarly on other
modern distributions.

Step 0: Prerequisites
---------------------

Please set up the following systems beforehand, we'll not explain them here (but see these links for
external installation guides):

* `Docker`_
* An SMTP server to send out mails, e.g. `Postfix`_ on your machine or some third-party server you
  have credentials for
* An HTTP reverse proxy, e.g. `nginx`_ or Apache to allow HTTPS connections
* A `MySQL`_ or `PostgreSQL`_ database server
* A `redis`_ server

We also recommend that you use a firewall, although this is not a pretalx-specific recommendation.
If you're new to Linux and firewalls, we recommend that you start with `ufw`_.

.. note:: Please, do not run pretalx without HTTPS encryption. You'll handle user data and thanks
          to `Let's Encrypt`_, SSL certificates are free these days. We also *do not* provide
          support for HTTP-exclusive installations except for evaluation purposes.

Step 1: Create a data directory
-------------------------------

First of all, you need to create a directory on your server that pretalx can use to store data
files::

    mkdir /var/pretalx-data


Step 2: Create a database
-------------------------

Next, we need a database and a database user. We can create these with any kind of database managing
tool or directly on our database's shell, e.g. for MySQL::

    mysql -u root -p
    mysql> CREATE DATABASE pretalx DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;
    mysql> GRANT ALL PRIVILEGES ON pretalx.* TO pretalx@'localhost' IDENTIFIED BY '*********';
    mysql> FLUSH PRIVILEGES;

Replace the asterisks with a password of your own. For MySQL, we will use a unix domain socket to
connect to the database. For PostgreSQL, be sure to configure the interface binding and your
firewall so that the docker container can reach PostgreSQL.

Step 3: Set up redis
--------------------

For caching and messaging, pretalx recommends using redis. In this small-scale setup we assume a
redis instance to be running on the same host. To avoid the hassle with network configurations and
firewalls, we recommend connecting to redis via a unix socket. To enable redis on unix sockets, add
the following to your ``/etc/redis/redis.conf``::

    unixsocket /var/run/redis/redis.sock
    unixsocketperm 777

Now restart redis-server::

    systemctl restart redis-server

.. warning:: Setting the socket permissions to 777 is a possible security problem. If you have
             untrusted users on your system or have high security requirements, please don't do
             this and let redis listen to a TCP socket instead. We recommend the socket approach
             because the TCP socket in combination with docker's networking can become an even
             worse security hole when configured slightly wrong. Read more about security on the
             `redis website`_.

             Another possible solution is to run `redis in docker`_ and link the containers using
             docker's networking features.

Step 4: Build the docker image
------------------------------

You need to build the Docker image yourself::

    git clone https://github.com/pretalx/pretalx.git
    cd pretalx/
    docker build -t pretalx/pretalx .

Step 5: Add a system service
----------------------------

We recommend starting the docker container using systemd to make sure it runs as expected after a
reboot. Create a file named ``/etc/systemd/system/pretalx.service`` with the following content::

    [Unit]
    Description=pretalx
    Requires=docker.service mysql.service redis-server.service
    After=docker.service mysql.service redis-server.service

    [Service]
    Restart=always
    ExecStart=/usr/bin/docker run -p 127.0.0.1:8089:80 \
        -e PRETALX_DB_TYPE=mysql \
        -e PRETALX_DB_NAME=pretalx \
        -e PRETALX_DB_USER=pretalx \
        -e PRETALX_DB_PASS=******* \
        -e PRETALX_DB_HOST=localhost \
        -e PRETALX_SITE_URL=https://pretalx.example.org \
        -e PRETALX_COOKIE_DOMAIN=pretalx.example.org \
        -e PRETALX_MAIL_FROM=pretalx@example.org \
        -e PRETALX_MAIL_HOST=172.17.0.1 \
        -e PRETALX_REDIS=unix:///tmp/redis.sock?db=3 \
        --name pretalx \
        -v /var/run/mysqld:/var/run/mysqld \
        -v /var/pretalx-data:/data \
        -v /var/run/redis/redis.sock:/tmp/redis.sock \
        -t pretalx/pretalx web
    ExecStop=/usr/bin/docker stop -t 2 pretalx ; /usr/bin/docker rm -f pretalx

    [Install]
    WantedBy=multi-user.target

If you're using PostgreSQL, set the database type to ``postgresql_psycopg2`` instead and leave out
the mysql volume mount. Of course, replace the domain names and passwords in the above file with
your own.

You can now run the following commands to enable and start the service::

    systemctl daemon-reload
    systemctl enable pretalx
    systemctl start pretalx

Now, create an admin user by running::

    docker exec -it pretalx pretalx createsuperuser


Step 6: SSL
-----------

The following snippet is an example on how to configure a nginx proxy for pretalx utilizing nginx'
caching features for static files::

    proxy_cache_path /tmp/nginx-pretalx levels=1:2 keys_zone=pretalx_static:10m inactive=60m max_size=250m;
    server {
        listen 80 default_server;
        listen [::]:80 ipv6only=on default_server;
        server_name pretalx.mydomain.com;
    }
    server {
        listen 443 default_server;
        listen [::]:443 ipv6only=on default_server;
        server_name pretalx.mydomain.com;

        ssl on;
        ssl_certificate /path/to/cert.chain.pem;
        ssl_certificate_key /path/to/key.pem;

        proxy_set_header Host $host;
	    proxy_set_header X-Forwarded-Proto https;
	    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        location /static/ {
            access_log off;
            proxy_pass http://localhost:8089;
            proxy_cache pretalx_static;
        }

        location /static/CACHE/ {
            expires 30d;
            add_header Cache-Control public;
            add_header Pragma public;
            proxy_cache pretalx_static;
            proxy_ignore_headers Cache-Control;
            proxy_cache_valid any 60m;
            add_header X-Proxy-Cache $upstream_cache_status;
            access_log off;
            proxy_pass http://localhost:8089;
        }

        location / {
            proxy_pass http://localhost:8089;
        }
    }


We recommend reading about setting `strong encryption settings`_ for your web server.

Yay, you made it! You should now be able to reach pretalx at https://<yourdomain>/orga/ and log in
as your newly created superuser. Set up an event, configure it as needed, and publish your CfP!

Next Steps: Updates
-------------------

.. warning:: While we try hard not to break anything, **please perform a backup before every upgrade**.

Updates are as simple as we could make them, but require at least a short downtime:

* Rebuild the docker image (git pull, then repeat the command from above)
* ``systemctl restart pretalx.service``

Restarting the service can take up to a minute (or more if the update requires changes to the
database and your database is large).

.. _Docker: https://docs.docker.com/engine/installation/linux/debian/
.. _Postfix: https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-postfix-as-a-send-only-smtp-server-on-ubuntu-16-04
.. _nginx: https://botleg.com/stories/https-with-lets-encrypt-and-nginx/
.. _Let's Encrypt: https://letsencrypt.org/
.. _MySQL: https://dev.mysql.com/doc/refman/5.7/en/linux-installation-apt-repo.html
.. _PostgreSQL: https://www.digitalocean.com/community/tutorials/how-to-install-and-use-postgresql-9-4-on-debian-8
.. _redis: http://blog.programster.org/debian-8-install-redis-server/
.. _ufw: https://en.wikipedia.org/wiki/Uncomplicated_Firewall
.. _redis website: http://redis.io/topics/security
.. _redis in docker: https://hub.docker.com/r/_/redis/
.. _strong encryption settings: https://mozilla.github.io/server-side-tls/ssl-config-generator/
