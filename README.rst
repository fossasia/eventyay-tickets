eventyay-tickets (ENext)
========================

.. image:: https://codecov.io/gh/fossasia/eventyay-tickets/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/pretix/pretix

Project status & release cycle
------------------------------

Welcome to the **Eventyay** project! The ticketing component of the system provides options for **ticket sales and event-related items** such as T-shirts. Eventyay has been in development since **2014**. Its ticketing component is based on a fork of **Pretix**.

ENext is the new and updated version of Eventyay with a unified codebase for the Tickets, Talk, and Videos components.

External Dependencies
---------------------

The *deb-packages.txt* file lists Debian packages we need to install.
If you are using Debian / Ubuntu, you can install them quickly with this command:

For traditional shell:

.. code-block:: bash

   $ xargs -a deb-packages.txt sudo apt install

For Nushell:

.. code-block:: nu

   > open deb-packages.txt | lines | sudo apt install ...$in


If you are using other Linux distros, please guess the corresponding package names for that list.

Other than that, please install `uv`_, the Python package manager.

Getting Started
---------------

1. **Clone the repository**:

   .. code-block:: bash

      git clone https://github.com/fossasia/eventyay-tickets.git

2. **Enter the project directory and app directory**:

   .. code-block:: bash

      cd eventyay-tickets/app

3. **Switch to the `enext` branch**:

   .. code-block:: bash

      git switch enext


4. **Install Python packages**

Use ``uv`` to create virtual environment and install Python packages at the same time.

  .. code-block:: sh

    uv sync --all-extras --all-groups


5. **Create a PostgreSQL database**

The default database name that the project needs is ``eventyay-db``. If you are using Linux, the simplest way
to work with database is to use its "peer" mode (no need to remember password).

Create a Postgres user with the same name as your Linux user:

.. code-block:: sh

   sudo -u postgres createuser -s $USER

(``-s`` means *superuser*)

Then just create a database owned by your user:

.. code-block:: sh

   createdb eventyay-db

From now on, you can do everything with the database without specifying password, host and port.

.. code-block:: sh

   dropdb eventyay-db
   psql eventyay-db

In case you cannot take adavantage of PostgreSQL *peer* mode, you need to create a *.env* file with these values:

.. code-block:: sh

   POSTGRES_USER=
   POSTGRES_PASSWORD=
   POSTGRES_HOST=
   POSTGRES_PORT=

6. **Create and configure Redis container**

Run a Redis container using Docker:

  .. code-block:: sh

   docker run -d --name eventyay-redis -p 6379:6379 redis:7

Then copy the default configuration file to the system directory (create the directory if it doesn't exist):

  .. code-block:: sh
   
   sudo mkdir -p /etc/eventyay
   sudo cp eventyay.cfg /etc/eventyay/eventyay.cfg

Edit the /etc/eventyay/eventyay.cfg file to configure Redis and Celery:

  .. code-block:: sh

   [redis]
   location=redis://localhost:6379/0
   sessions=true

   [celery]
   backend=redis://localhost:6379/1
   broker=redis://localhost:6379/2


7. **Activate virtual environment**

After running ``uv sync```, ``uv`` will activate the virtual environment. But if you are back
to work on the project another, we don't run ``uv``, then we activate the virtual environment by:


  .. code-block:: sh

    . .venv/bin/activate


8. **Initialize the database**:

   .. code-block:: bash

      python manage.py migrate

9. **Create a superuser account** (for accessing the admin panel):

   .. code-block:: bash

      python manage.py createsuperuser

10. **Run the development server**:

    .. code-block:: bash

       python manage.py runserver


Notes: If you get permission errors for eventyay/static/CACHE, make sure that the directory and
all below it are own by you.

Docker based development
------------------------

We assume your current working directory is the checkout of this repo.

1. **Create .env.dev**

   .. code-block:: bash

      cp deployment/env.dev-sample .env.dev

2. **Edit .env.dev**

   Only if necessary

3. **Make sure you don't have some old volumes hanging around**

   This is only necessary the first time, or if you have strange behaviour.
   This removes the database volume and triggers a complete reinitialization.
   After that, you have to run migrate and createsuperuser again!

   .. code-block:: bash

      docker volume rm eventyay_postgres_data_dev eventyay_static_volume

4. **Build and run the images**

   .. code-block:: bash

      docker compose up -d --build

5. **Create a superuser account** (for accessing the admin panel):

   This should be necessary only once, since the database is persisted 
   as docker volume. If you see strange behaviour, see the point 3.
   on how to reset.

   .. code-block:: bash

      docker exec -ti eventyay-next-web python manage.py createsuperuser

6. **Visit the site**

   Open `http://localhost:8000` in a browser.

7. **Checking the logs**

   .. code-block:: bash

      docker compose logs -f


8. **Shut down**

   To shut down the development docker deployment, run

   .. code-block:: bash

      docker compose down

The directory `app/eventyay` is mounted into the docker, thus live editing is supported.


Deployment
----------

* copy all of the `deployment` directory onto the server (eg. as `/home/fossasia/enext`)
* prepare the used volumes in docker-compose: one for static files and one for
  the postgres database. Create on the server:
        /home/fossasia/enext/data/static
        /home/fossasia/enext/data/postgres
  and
        chown 100:101 /home/fossasia/enext/data/static
* copy `env.prod-sample` to `.env` in `/home/fossasia/enext`, and edit it to your
  liking
* copy `nginx/enext-direct` to your system `/etc/nginx/sites-available`
  The file needs to be adjusted if the `enext` dir is NOT in `/home/fossasia`!
* Link the `enext-direct` file into `/etc/nginx/sites-enabled`
* Restart nginx
* Run
        docker compose up -d

Support
-------

This project is **free and open-source software**. Professional support is available to customers of the **hosted Eventyay service** or **Eventyay enterprise offerings**. If you are interested in commercial support, hosting services, or supporting this project financially, please go to `eventyay.com`.

Contributing
------------

Please look through our issues and start contributing.

License
-------

The code in this repository is published under the terms of the **Apache 2 License**.
See the LICENSE file for the complete license text.

This project is maintained by **FOSSASIA**. See the AUTHORS file for a list of all the awesome contributors of this project.

.. _uv: https://docs.astral.sh/uv/getting-started/installation/
.. _installation guide: https://docs.eventyay.com/en/latest/admin/installation/index.html
.. _eventyay.com: https://eventyay.com
.. _blog: https://blog.eventyay.com


