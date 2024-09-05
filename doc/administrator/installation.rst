.. _installation:

Installation
============

This guide will help you to install pretalx on Linux. This setup is suitable to
support events in usual sizes, but the guide does not go into performance
tuning or customisation options beyond the standard settings.

.. warning:: While we try to make it straightforward to run pretalx, it still
             requires some Linux experience to get it right, particularly to
             make sure that standard security practices are followed. If
             you’re not feeling comfortable managing a Linux server, check
             out our hosting and service offers at `pretalx.com`_.

For the more automation-savvy, we also provide an `Ansible role`_ that follows
this guide. If you prefer a docker setup, there is a `docker-compose setup`_.
Please note that the docker setup is community provided and not officially
supported.

Step 0: Prerequisites
---------------------

Please set up the following systems beforehand. We can’t go into their use
and configuration here, but please have a look at the linked pages.

* **Python 3.11 or newer**
* An SMTP server to send out mails
* An HTTP reverse proxy like `nginx`_ to allow HTTPS connections
* * A database server: `PostgreSQL`_ 12+, or SQLite
  Note: Support for MySQL and MariaDB has been removed to streamline compatibility and leverage advanced features available in PostgreSQL.
  3. Given the choice, we’d recommend to use PostgreSQL.
* A `redis`_ server, if you want to use pretalx with an asynchronous task
  runner or improved caching.
* `nodejs`_ and npm (usually bundled with nodejs). You’ll need a `supported
  version of nodejs`_.

.. highlight:: console

Please ensure that the environment used to run pretalx is configured to work
with non-ASCII file names. You can check this by running::

    $ python -c "import sys; print(sys.getfilesystemencoding())"
    utf-8

Step 1: Unix user
-----------------

.. hint:: All code lines prepended with a ``#`` symbol are commands that you
          need to execute on your server as the ``root`` user (e.g. using
          ``sudo``); you should run all lines prepended with a ``$`` symbol as
          the ``pretalx`` user.

As we do not want to run pretalx as root, we first create a new unprivileged user::

    # adduser pretalx --disabled-password --home /var/pretalx


Step 2: Database setup
----------------------

pretalx runs with PostgreSQL or SQLite. If you’re using
SQLite, you can skip this step, as there is no need to set up the database.

We recommend using PostgreSQL. This is how you can set up a database for your
pretalx installation – if you do not use PostgreSQL, please refer to the
appropriate documentation on how to set up a database::

  # sudo -u postgres createuser pretalx -P
  # sudo -u postgres createdb -O pretalx pretalx

Make sure that your database encoding is UTF-8. You can check with this command::

  # sudo -u postgres psql -c 'SHOW SERVER_ENCODING'

.. highlight:: sql


Step 3: Package dependencies
----------------------------

Besides the packages above, you might need local system packages to build and
run pretalx. We cannot maintain an up-to-date dependency list for all Linux
flavours – on Ubuntu-like systems, you will need packages like:

- ``build-essential``
- ``libssl-dev``
- ``python3-dev``
- ``gettext``


Step 4: Configuration
---------------------

.. highlight:: console

Now we’ll create a configuration directory and configuration file for pretalx::

    # mkdir /etc/pretalx
    # touch /etc/pretalx/pretalx.cfg
    # chown -R pretalx:pretalx /etc/pretalx/
    # chmod 0600 /etc/pretalx/pretalx.cfg

This snippet can get you started with a basic configuration in your
``/etc/pretalx/pretalx.cfg`` file:

.. literalinclude:: ../../src/pretalx.example.cfg
   :language: ini

Refer to :ref:`configure` for a full list of configuration options – the
options above are only the ones you’ll likely need to get started.

Step 5: Installation
--------------------

For your Python installation, you’ll want to use a virtual environment to
isolate the installation from system packages. Set up your virtual environment
like this – you’ll only have to run this command once (that is, only once per
Python version – when you upgrade from Python 3.13 to 3.14, you’ll need to
remove the old ``venv`` directory and create it again the same way)::

    $ python -m venv /var/pretalx/venv

Now, activate the virtual environment – you’ll have to run this command once
per session whenever you’re interacting with ``python``, ``pip`` or
``pretalx``::

    $ source /var/pretalx/venv/bin/activate

Now, upgrade your pip and then install the required Python packages::

    (venv)$ pip install --user -U pip setuptools wheel gunicorn

.. note:: You may need to replace all following mentions of ``pip`` with ``pip3``.

+-----------------+------------------------------------------------------------------------+
| Database        | Command                                                                |
+=================+========================================================================+
| SQLite          | ``pip install --user --upgrade-strategy eager -U pretalx``             |
+-----------------+------------------------------------------------------------------------+
| PostgreSQL      | ``pip install --user --upgrade-strategy eager -U "pretalx[postgres]"`` |
+-----------------+------------------------------------------------------------------------+

If you intend to run pretalx with asynchronous task runners or with redis as
cache server, you can add ``[redis]`` to the installation command, which will
pull in the appropriate dependencies. Please note that you should also use
``pretalx[redis]`` when you upgrade pretalx in this case.

We also need to create a data directory::

    $ mkdir -p /var/pretalx/data/media

We compile static files and translation data and create the database structure::

    (venv)$ python -m pretalx migrate
    (venv)$ python -m pretalx rebuild

Now, create a user with administrator rights, an organiser and a team by running::

    (venv)$ python -m pretalx init

Step 6: Starting pretalx as a service
-------------------------------------

.. highlight:: ini

We recommend starting pretalx using systemd to make sure it starts up after a
reboot. Create a file named ``/etc/systemd/system/pretalx-web.service``, and
adjust the content to fit your system::

    [Unit]
    Description=pretalx web service
    After=network.target

    [Service]
    User=pretalx
    Group=pretalx
    WorkingDirectory=/var/pretalx
    ExecStart=/var/pretalx/.local/bin/gunicorn pretalx.wsgi \
                          --name pretalx --workers 4 \
                          --max-requests 1200  --max-requests-jitter 50 \
                          --log-level=info --bind=127.0.0.1:8345
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target

If you decide to use Celery (giving you asynchronous execution for long-running
tasks), you’ll also need a second service
``/etc/systemd/system/pretalx-worker.service`` with the following content::

    [Unit]
    Description=pretalx background worker
    After=network.target

    [Service]
    User=pretalx
    Group=pretalx
    ExecStart=/var/pretalx/venv/bin/celery -A pretalx.celery_app worker -l info
    WorkingDirectory=/var/pretalx
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target

.. highlight:: console

You can now run the following commands to enable and start the services::

    # systemctl daemon-reload
    # systemctl enable pretalx-web pretalx-worker
    # systemctl start pretalx-web pretalx-worker

Step 7: SSL
-----------

.. highlight:: nginx

You’ll need to set up an HTTP reverse proxy to handle HTTPS connections. It doesn’t
particularly matter which one you use, as long as you make sure to use `strong
encryption settings`_. Your proxy should

* serve all requests exclusively over HTTPS
* set the ``X-Forwarded-For`` and ``X-Forwarded-Proto`` headers
* set the ``Host`` header
* serve all requests for the ``/static/`` and ``/media/`` paths from the
  directories you set up in the previous step, without permitting directory
  listings or traversal
* pass requests to the gunicorn server you set up in the previous step

The following snippet is an example on how to configure an nginx proxy for pretalx::

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

        gzip off;
        add_header Referrer-Policy same-origin;
        add_header X-Content-Type-Options nosniff;

        location / {
            proxy_pass http://localhost:8345/;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header Host $http_host;
        }

        location /media/ {
            gzip on;
            alias /var/pretalx/data/media/;
            add_header Content-Disposition 'attachment; filename="$1"';
            expires 7d;
            access_log off;
        }

        location /static/ {
            gzip on;
            alias /path/to/static.dist/;
            access_log off;
            expires 365d;
            add_header Cache-Control "public";
        }
    }


Step 8: Check the installation
-------------------------------

.. highlight:: console

You can make sure the web interface is up and look for any issues with::

    # journalctl -u pretalx-web

If you use Celery, you can do the same for the worker processes (for example in
case the emails are not sent)::

    # journalctl -u pretalx-worker

If you’re looking for errors, check the pretalx log. You can find the logging
directory in the start-up output.

Once pretalx is up and running, you can also find up to date administrator information
at https://pretalx.yourdomain.com/orga/admin/.

Step 9: Provide periodic tasks
------------------------------

There are a couple of things in pretalx that should be run periodically. It
doesn’t matter how you run them, so you can go with your choice of periodic
tasks, be they systemd timers, cron, or something else entirely.

In the same environment as you ran the previous pretalx commands (e.g. the
``pretalx`` user, using either the executable paths in the
``/var/pretalx/venv`` directory, or running ``/var/pretalx/venv/bin/activate``
first), you should run

- ``python -m pretalx runperiodic`` somewhere every five minutes and once per hour.
- ``python -m pretalx clearsessions`` about once a month.

You could for example configure the ``pretalx`` user cron like this::

  */10 * * * * /var/pretalx/venv/bin/python -m pretalx runperiodic

Next Steps
----------

You made it! You should now be able to reach pretalx at
https://pretalx.yourdomain.com/orga/ Log in with the administrator account you
configured above, and create your first event!

Check out :ref:`configure` for details on the available configuration options.

If you want to read about updates, backups, and monitoring, head over to our
:ref:`maintenance` documentation!

.. _Ansible role: https://github.com/pretalx/ansible-pretalx
.. _nginx: https://botleg.com/stories/https-with-lets-encrypt-and-nginx/
.. _Let’s Encrypt: https://letsencrypt.org/
.. _PostgreSQL: https://www.postgresql.org/docs/
.. _redis: https://redis.io/documentation
.. _ufw: https://en.wikipedia.org/wiki/Uncomplicated_Firewall
.. _strong encryption settings: https://mozilla.github.io/server-side-tls/ssl-config-generator/
.. _docker-compose setup: https://github.com/pretalx/pretalx-docker
.. _pretalx.com: https://pretalx.com
.. _nodejs: https://github.com/nodesource/distributions/blob/master/README.md
.. _supported version of nodejs: https://nodejs.org/en/about/previous-releases
