.. _installation:

Installation
============

This guide will help you to install pretalx on Linux, as long as the
prerequisites are present.

We also provide an `Ansible role`_ that follows this guide.  If you prefer a
docker setup, please use our `docker-compose setup`_. (Please note that the
pretalx community provides the docker setup. It is not supported by the pretalx
team.)

Step 0: Prerequisites
---------------------

Please set up the following systems beforehand. We will not explain their use
and configuration here (but have a look at the linked pages).

* **Python 3.6 or newer** and a ``pip`` to match. You can use ``python -V`` and
  ``pip3 -V`` to check.
* An SMTP server to send out mails
* An HTTP reverse proxy, e.g. `nginx`_ or Apache to allow HTTPS connections
* A `MySQL`_ (5.6 or higher) or `PostgreSQL`_ (9.6 or higher) database server.
  You can use SQLite, but we strongly recommend not to run SQLite in
  production.
* A `redis`_ server, if you want to use pretalx with an asynchronous task
  runner or improved caching.

We assume that you also have the usual security measures in place, such as a
firewall. If you're new to Linux and firewalls, we recommend that you start
with `ufw`_.

Please ensure that the environment used to run pretalx is configured to work
with non-ASCII file names. You can check this by running::

    python -c "import sys; print(sys.getfilesystemencoding())"

This should output ``"utf-8"``.

.. note:: Please do not run pretalx without HTTPS encryption. You'll handle user data and thanks
          to `Let's Encrypt`_, SSL certificates are free these days. We also *do not* provide
          support for HTTP-exclusive installations except for evaluation purposes.

Step 1: Unix user
-----------------

.. hint:: All code lines prepended with a ``#`` symbol are commands that you
          need to execute on your server as ``root`` user (e.g. using
          ``sudo``); you should run all lines prepended with a ``$`` symbol as
          the unprivileged user.

As we do not want to run pretalx as root, we first create a new unprivileged user::

    # adduser pretalx --disabled-password --home /var/pretalx


Step 2: Database setup
----------------------

Having the database server installed, we still need a database and a database
user. We recommend using PostgreSQL. pretalx also works (and runs tests
against) MariaDB and SQLite. If you do not use PostgreSQL, please refer to the
appropriate documentation on how to set up a database. For PostgreSQL, run
these commands::

  # sudo -u postgres createuser pretalx -P
  # sudo -u postgres createdb -O pretalx pretalx

When using MySQL, make sure you set the character set of the database to ``utf8mb4``, e.g. like this::

    mysql > CREATE DATABASE pretalx DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unic


Step 3: Package dependencies
----------------------------

Besides the packages above, you might need local system packages to build and
run pretalx. We cannot maintain an up-to-date dependency list for all Linux
flavours, but we can offer you a list for Ubuntu. You should be able to find
the appropriate packages on your system from there:

On Ubuntu-esque systems, you will need packages like:

- ``build-essential``
- ``libssl-dev``
- ``python3-dev``
- ``gettext``
- ``libmysqlclient-dev`` if you use MariaDB

pretalx requires Python 3.6 or Python 3.7. If you cannot find one of these
versions for your system, you can build it from source.

.. note:: You may need to replace all following mentions of ``pip`` with
          ``pip3.6`` or ``pip3``.


Step 4: Configuration
---------------------

Now we'll create a configuration directory and configuration file for pretalx::

    # mkdir /etc/pretalx
    # touch /etc/pretalx/pretalx.cfg
    # chown -R pretalx:pretalx /etc/pretalx/
    # chmod 0600 /etc/pretalx/pretalx.cfg

Fill the configuration file ``/etc/pretalx/pretalx.cfg`` with the following
content. But don't forget to adjust it to your environment:

.. literalinclude:: ../../src/pretalx.example.cfg
   :language: ini

Check out :ref:`configure` for details on the available configuration options.

Step 5: Installation
--------------------

Please execute the following steps as the ``pretalx`` user. This isolates the
pretalx environment from your global Python versions and binaries::

    $ pip install --user -U pip setuptools wheel gunicorn

pretalx works with your choice of database backends – we recommend using
PostgreSQL, but MySQL and SQLite work as well. Use this command to install the
database driver (unless you use SQLite, which has its driver built in):

+------------+-------------------------------------------+
| Database   | pip package                               |
+============+===========================================+
| PostgreSQL | ``pip install --user -U psycopg2-binary`` |
+------------+-------------------------------------------+
| MySQL      | ``pip install --user -U mysqlclient``     |
+------------+-------------------------------------------+
| Oracle     | ``pip install --user -U cx_Oracle``       |
+------------+-------------------------------------------+

Now we will install pretalx itself::

    $ pip install --user -U pretalx

If you intend to run pretalx with asynchronous task runners or with redis as
cache server, you can install ``pretalx[redis]`` instead, which will pull in
the appropriate dependencies. Please note that you should also use
``pretalx[redis]`` when you upgrade pretalx in this case.

We also need to create a data directory::

    $ mkdir -p /var/pretalx/data/media

We compile static files and translation data and create the database structure::

    $ python -m pretalx migrate
    $ python -m pretalx rebuild

Now, create a user with administrator rights, an organiser and a team by running::

    $ python -m pretalx init

Step 6: Starting pretalx as a service
-------------------------------------

We recommend starting pretalx using systemd to make sure it starts up after a reboot. Create a file
named ``/etc/systemd/system/pretalx-web.service`` with the following content::

    [Unit]
    Description=pretalx web service
    After=network.target

    [Service]
    User=pretalx
    Group=pretalx
    WorkingDirectory=/var/pretalx/.local/lib/python3.6/site-packages/pretalx
    ExecStart=/var/pretalx/.local/bin/gunicorn pretalx.wsgi \
                          --name pretalx --workers 4 \
                          --max-requests 1200  --max-requests-jitter 50 \
                          --log-level=info --bind=127.0.0.1:8345
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target

If you decide to use Celery (giving you asynchronous execution for long-running
tasks), you'll also need a second service
``/etc/systemd/system/pretalx-worker.service`` with the following content::

    [Unit]
    Description=pretalx background worker
    After=network.target

    [Service]
    User=pretalx
    Group=pretalx
    WorkingDirectory=/var/pretalx/.local/lib/python3.6/site-packages/pretalx
    ExecStart=/var/pretalx/.local/bin/celery -A pretalx.celery_app worker -l info
    WorkingDirectory=/var/pretalx
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target

You can now run the following commands to enable and start the services::

    # systemctl daemon-reload
    # systemctl enable pretalx-web pretalx-worker
    # systemctl start pretalx-web pretalx-worker

Step 7: SSL
-----------

The following snippet is an example on how to configure a nginx proxy for pretalx::

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

        add_header Referrer-Options same-origin;
        add_header X-Content-Type-Options nosniff;

        location / {
            proxy_pass http://localhost:8345/;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header Host $http_host;
        }

        location /media/ {
            alias /var/pretalx/data/media/;
            add_header Content-Disposition 'attachment; filename="$1"';
            expires 7d;
            access_log off;
        }

        location /static/ {
            alias /path/to/static.dist/;
            access_log off;
            expires 365d;
            add_header Cache-Control "public";
        }
    }

We recommend reading about setting `strong encryption settings`_ for your web server.

You've made it! You should now be able to reach pretalx at https://pretalx.yourdomain.com/orga/
Log in as the administrator you configured above, and create your first event!

Step 8: Check the installation
-------------------------------

You can make sure the web interface is up and look for any issues with::

    # journalctl -u pretalx-web

If you use Celery, you can do the same for the worker processes (for example in
case the emails are not sent)::

    # journalctl -u pretalx-worker

If you're looking for errors, check the pretalx log. You can find the logging
directory in the start-up output.

Step 9: Provide periodic tasks
------------------------------

There are a couple of things in pretalx that should be run periodically. It
doesn't matter how you run them, so you can go with your choice of periodic
tasks, be they systemd timers, cron, or something else entirely.

In the same environment as you ran the previous pretalx commands (e.g. the
``pretalx`` user), you should run

- ``python -m pretalx runperiodic`` about every five minutes.
- ``python -m pretalx clearsessions`` about once a month.

Next Steps
----------

Check out :ref:`configure` for details on the available configuration options.

If you want to read about updates, backups, and monitoring, head over to our
:ref:`maintenance` documentation!

.. _Ansible role: https://github.com/pretalx/ansible-pretalx
.. _nginx: https://botleg.com/stories/https-with-lets-encrypt-and-nginx/
.. _Let's Encrypt: https://letsencrypt.org/
.. _MySQL: https://dev.mysql.com/doc/refman/5.7/en/linux-installation-apt-repo.html
.. _PostgreSQL: https://www.postgresql.org/docs/
.. _redis: https://redis.io/documentation
.. _ufw: https://en.wikipedia.org/wiki/Uncomplicated_Firewall
.. _strong encryption settings: https://mozilla.github.io/server-side-tls/ssl-config-generator/
.. _docker-compose setup: https://github.com/pretalx/pretalx-docker
