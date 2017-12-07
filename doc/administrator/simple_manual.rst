Simple manual installation
==========================

This guide will help you to install pretalx on a Linux distribution. It should be
compatible with **Debian 8.0** and above, as well as similarly modern distributions.
By "simple", we mean a setup that will run with fairly few moving parts, and that
will be suitable to smaller events and not extreme amounts of traffic.

We also provide an `ansible role`_ that basically follows this guide, in case you
already have an ansible-based setup.

Step 0: Prerequisites
---------------------

Please set up the following systems beforehand, we'll not explain them here (but see these links for
external installation guides):

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

Step 1: Unix user
-----------------

As we do not want to run pretalx as root, we first create a new unprivileged user::

    # adduser pretalx --disabled-password --home /var/pretalx

In this guide, all code lines prepended with a ``#`` symbol are commands that you need to execute on your server as
``root`` user (e.g. using ``sudo``); all lines prepended with a ``$`` symbol should be run by the unprivileged user.


Step 2: Database setup
----------------------

Having the database server installed, we still need a database and a database user. We can create these with any kind
of database managing tool or directly on our database's shell, e.g. for MySQL::

    $ mysql -u root -p
    mysql> CREATE DATABASE pretalx DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;
    mysql> GRANT ALL PRIVILEGES ON pretalx.* TO pretalx@'localhost' IDENTIFIED BY '*********';
    mysql> FLUSH PRIVILEGES;

Replace the asterisks with a password of your own. For MySQL, we will use a unix domain socket to
connect to the database. For PostgreSQL, be sure to configure the interface binding and your
firewall so that the docker container can reach PostgreSQL.


Step 3: Package dependencies
----------------------------

To build and run pretalx, you will need the following debian packages beyond the dependencies
mentioned above::

    # apt-get install git build-essential python-virtualenv libssl-dev gettext libmysqlclient-dev

Step 4: Configuration
---------------------

We now create a config directory and config file for pretalx::

    # mkdir /etc/pretalx
    # touch /etc/pretalx/pretalx.cfg
    # chown -R pretalx:pretalx /etc/pretalx/
    # chmod 0600 /etc/pretalx/pretalx.cfg

Fill the configuration file ``/etc/pretalx/pretalx.cfg`` with the following content (adjusted to your environment)::

.. literalinclude:: ../../src/pretalx.example.cfg
   :language: ini

Step 5: Installation
--------------------

Now we will install pretalx itself. The following steps are to be executed as the ``pretalx`` user. Before we
actually install pretalx, we will create a virtual environment to isolate the python packages from your global
python installation::

    $ virtualenv -p python3 /var/pretalx/venv
    $ source /var/pretalx/venv/bin/activate
    (venv)$ pip3 install -U pip setuptools wheel pretalx redis gunicorn

We also need to create a data directory::

    (venv)$ mkdir -p /var/pretalx/data/media

Finally, we compile static files and translation data and create the database structure::

    (venv)$ python -m pretalx migrate
    (venv)$ python -m pretalx rebuild

Now, create an admin user by running::

    (venv)$ python -m pretalx createsuperuser

Step 6: Starting pretalx as a service
-------------------------------------

We recommend starting pretalx using systemd to make sure it runs correctly after a reboot. Create a file
named ``/etc/systemd/system/pretalx-web.service`` with the following content::

    [Unit]
    Description=pretalx web service
    After=network.target

    [Service]
    User=pretalx
    Group=pretalx
    Environment="VIRTUAL_ENV=/var/pretalx/venv"
    Environment="PATH=/var/pretalx/venv/bin:/usr/local/bin:/usr/bin:/bin"
    ExecStart=/var/pretalx/venv/bin/gunicorn pretalx.wsgi \
                          --name pretalx --workers 5 \
                          --max-requests 1200  --max-requests-jitter 50 \
                          --log-level=info --bind=127.0.0.1:8345
    WorkingDirectory=/var/pretalx
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target

For background tasks we need a second service ``/etc/systemd/system/pretalx-worker.service`` with the following content::

    [Unit]
    Description=pretalx background worker
    After=network.target

    [Service]
    User=pretalx
    Group=pretalx
    Environment="VIRTUAL_ENV=/var/pretalx/venv"
    Environment="PATH=/var/pretalx/venv/bin:/usr/local/bin:/usr/bin:/bin"
    ExecStart=/var/pretalx/venv/bin/celery -A pretalx.celery_app worker -l info
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
            expires 7d;
            access_log off;
        }

        location /static/ {
            alias /var/pretalx/venv/lib/python3.6/site-packages/pretalx/static.dist/;
            access_log off;
            expires 365d;
            add_header Cache-Control "public";
        }
    }

.. note:: Remember to replace the ``python3.6`` in the ``/static/`` path in the config 
          above with your python version.

We recommend reading about setting `strong encryption settings`_ for your web server.

Yay, you are done! You should now be able to reach pretalx at https://pretalx.yourdomain.com/control/ and log in as
the superuser you configured above. You can now create an event, and off you go!


Next Steps: Updates
-------------------

.. warning:: While we try hard not to break things, **please perform a backup before every upgrade**.

To upgrade to a new pretalx release, pull the latest code changes and run the following commands::

    $ source /var/pretalx/venv/bin/activate
    (venv)$ pip3 install -U pretalx gunicorn
    (venv)$ python -m pretalx migrate
    (venv)$ python -m pretalx rebuild
    # systemctl restart pretalx-web pretalx-worker


.. _ansible role: https://github.com/pretalx/ansible-pretalx
.. _Postfix: https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-postfix-as-a-send-only-smtp-server-on-ubuntu-16-04
.. _nginx: https://botleg.com/stories/https-with-lets-encrypt-and-nginx/
.. _Let's Encrypt: https://letsencrypt.org/
.. _MySQL: https://dev.mysql.com/doc/refman/5.7/en/linux-installation-apt-repo.html
.. _PostgreSQL: https://www.digitalocean.com/community/tutorials/how-to-install-and-use-postgresql-9-4-on-debian-8
.. _redis: http://blog.programster.org/debian-8-install-redis-server/
.. _ufw: https://en.wikipedia.org/wiki/Uncomplicated_Firewall
