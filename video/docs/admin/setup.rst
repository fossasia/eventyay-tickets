.. highlight:: none

Installation guide
==================

This guide describes the installation of a small-scale installation of venueless using docker. By small-scale, we mean
that everything is being run on one host, and you don't expect many thousands of participants for your events.
It is absolutely possible to run venueless without docker if you have some experience working with Django and JavaScript
projects, but we currently do not provide any documentation or support for it. At this time, venueless is a young,
fast-moving project, and we do not have the capacity to keep multiple different setup guides up to date.

.. warning:: venueless is still a work in progress and anything about deploying it might change. While we tried to
             give a good tutorial here, installing venueless will **require solid Linux experience** to get it right, and
             venueless is only really useful in combination with other pieces of software (eg. BigBlueButton, live streaming servers, …)
             which are not explained here and complex to install on their own. If this is too much for you, please
             **reach out to hello@venueless.org** to talk about commercial support or our SaaS offering.

We tested this guide on the Linux distribution **Debian 10.0** but it should work very similar on other
modern distributions, especially on all systemd-based ones.

Requirements
------------

Please set up the following systems beforehand, we'll not explain them here (but see these links for external
installation guides):

* `Docker`_
* A HTTP reverse proxy, e.g. `nginx`_ to allow HTTPS and websocket connections
* A `PostgreSQL`_ 11+ database server
* A `redis`_ server

This guide will assume PostgreSQL and redis are running on the host system. You can of course run them as docker
containers as well if you prefer, you just need to adjust the hostnames in venueless' configuration file.
We also recommend that you use a firewall, although this is not a venueless-specific recommendation. If you're new to
Linux and firewalls, we recommend that you start with `ufw`_.

.. note:: Please, do not run venueless without HTTPS encryption. You'll handle user data and thanks to `Let's Encrypt`_
          SSL certificates can be obtained for free these days. We also *do not* provide support for HTTP-only
          installations except for evaluation purposes.

On this guide
-------------

All code lines prepended with a ``#`` symbol are commands that you need to execute on your server as ``root`` user;
all lines prepended with a ``$`` symbol can also be run by an unprivileged user.

Data files
----------

First of all, you need to create a directory on your server that venueless can use to store files such as logs and make
that directory writable to the user that runs venueless inside the docker container::

    # mkdir /var/venueless-data
    # chown -R 15371:15371 /var/venueless-data

Database
--------

Next, we need a database and a database user. We can create these with any kind of database managing tool or directly on
your ``psql`` shell::

    # sudo -u postgres createuser -P venueless
    # sudo -u postgres createdb -O venueless venueless

Make sure that your database listens on the network. If PostgreSQL runs on the same host as docker, but not inside a
docker container, we recommend that you just listen on the Docker interface by changing the following line in
``/etc/postgresql/<version>/main/postgresql.conf``::

    listen_addresses = 'localhost,172.17.0.1'

You also need to add a new line to ``/etc/postgresql/<version>/main/pg_hba.conf`` to allow network connections to this
user and database::

    host    venueless          venueless          172.17.0.1/16           md5

Restart PostgreSQL after you changed these files::

    # systemctl restart postgresql

If you have a firewall running, you should also make sure that port 5432 is reachable from the ``172.17.0.1/16`` subnet.

Redis
-----

For caching and many of our real-time features, we rely on redis as a powerful key-value store. Again, you will
need to configure redis to listen on the correct interface by setting a parameter in ``/etc/redis/redis.conf``.
Additionally, we strongly recommend setting an authentication password::

    bind 172.17.0.1 127.0.0.1
    requirepass mysecurepassword

Now restart redis-server::

    # systemctl restart redis-server

Config file
-----------

We now create a config directory and config file for venueless::

    # mkdir /etc/venueless
    # touch /etc/venueless/venueless.cfg
    # chown -R 15371:15371 /etc/venueless/
    # chmod 0700 /etc/venueless/venueless.cfg

Fill the configuration file ``/etc/venueless/venueless.cfg`` with the following content (adjusted to your environment)::

    [database]
    backend=postgresql
    name=venueless
    user=venueless
    ; Replace with the password you chose above
    password=*********
    ; In most docker setups, 172.17.0.1 is the address of the docker host. Adjuts
    ; this to wherever your database is running, e.g. the name of a linked container
    host=172.17.0.1

    [redis]
    ; In most docker setups, 172.17.0.1 is the address of the docker host. Adjuts
    ; this to wherever your database is running, e.g. the name of a linked container
    host=172.17.0.1
    ; Replace with the password you chose above
    auth=mysecurepassword


Docker image and service
------------------------

First of all, download the latest venueless image by running::

    $ docker pull venueless/venueless:latest

We recommend starting the docker container using systemd to make sure it runs correctly after a reboot. Create a file
named ``/etc/systemd/system/venueless.service`` with the following content::

    [Unit]
    Description=venueless
    After=docker.service
    Requires=docker.service

    [Service]
    TimeoutStartSec=0
    ExecStartPre=-/usr/bin/docker kill %n
    ExecStartPre=-/usr/bin/docker rm %n
    ExecStart=/usr/bin/docker run --name %n -p 8002:80 \
        -v /var/venueless-data:/data \
        -v /etc/venueless:/etc/venueless \
        --sysctl net.core.somaxconn=4096 \
        venueless/venueless:latest all
    ExecStop=/usr/bin/docker stop %n

    [Install]
    WantedBy=multi-user.target

You can now run the following commands to enable and start the service::

    # systemctl daemon-reload
    # systemctl enable venueless
    # systemctl start venueless

SSL
---

The following snippet is an example on how to configure a nginx proxy for venueless::

    server {
        listen 80 default_server;
        listen [::]:80 ipv6only=on default_server;
        server_name venueless.mydomain.com;
        return 301 https://$host$request_uri;
    }
    server {
        listen 443 default_server;
        listen [::]:443 ipv6only=on default_server;
        server_name venueless.mydomain.com;

        ssl on;
        ssl_certificate /path/to/cert.chain.pem;
        ssl_certificate_key /path/to/key.pem;

        location / {
            proxy_set_header    Host $host;
            proxy_set_header    X-Real-IP $remote_addr;
            proxy_set_header    X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header    X-Forwarded-Proto $scheme;
            proxy_http_version 1.1;
            proxy_set_header	Upgrade $http_upgrade;
            proxy_set_header 	Connection "upgrade";
            proxy_set_header 	X-Forwarded-Ssl on;
            proxy_read_timeout  300s;
            proxy_redirect 		http:// https://;
            proxy_pass 			http://localhost:8002;
        }
    }


We recommend reading about setting `strong encryption settings`_ for your web server.

Create your world
-----------------

Everything in venueless happens in a **world**. A world basically represents your digital event, with everything it includes:
Users, settings, rooms, and so on.

To create your first world, execute the following command and answer its questions.
Right now, every world needs its own domain to run on::

    $ docker exec -it venueless.service venueless create_world
    Enter the internal ID for the new world (alphanumeric): myevent2020
    Enter the title for the new world: My Event 2020
    Enter the domain of the new world (e.g. myevent.example.org): venueless.mydomain.com
    World created.
    Default API keys: [{'issuer': 'any', 'audience': 'venueless', 'secret': 'zvB7hI28vbrI7KtsRnJ1TZBSN3DvYdoy9VoJGLI1ouHQP5VtRG3U6AgKJ9YOqKNU'}]

That's it! You should now be able to access venueless on the configured domain.

Cronjobs
--------

If you have multiple BigBlueButton servers, you should add a cronjob that polls the current meeting and user numbers for
the BBB servers to update the load balancer's cost function::

    * * * * *   docker exec venueless.service venueless bbb_update_cost

Also, the following cronjob performs various cleanup tasks::

    */10 * * * *   docker exec venueless.service venueless cleanup

Updates
-------

.. warning:: While we try hard not to break things, **please perform a backup before every upgrade**.

Updates are fairly simple, but require at least a short downtime::

    # docker pull venueless/venueless:latest
    # systemctl restart venueless.service

Restarting the service can take a few seconds, especially if the update requires changes to the database.


.. _Docker: https://docs.docker.com/engine/installation/linux/debian/
.. _Postfix: https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-postfix-as-a-send-only-smtp-server-on-ubuntu-16-04
.. _nginx: https://botleg.com/stories/https-with-lets-encrypt-and-nginx/
.. _Let's Encrypt: https://letsencrypt.org/
.. _PostgreSQL: https://www.tecmint.com/install-postgresql-database-in-debian-10/
.. _redis: https://www.digitalocean.com/community/tutorials/how-to-install-and-secure-redis-on-debian-10
.. _ufw: https://en.wikipedia.org/wiki/Uncomplicated_Firewall
.. _redis website: https://redis.io/topics/security
.. _redis in docker: https://hub.docker.com/r/_/redis/
.. _strong encryption settings: https://mozilla.github.io/server-side-tls/ssl-config-generator/
